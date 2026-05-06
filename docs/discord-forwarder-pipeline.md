# Discord Channel Forwarder + ekstenzibilna pipeline

Minimalen, samostojen vzorec za **discord.py 2.x** — preposlje sporočila iz enega kanala v drugega in dovoli pozneje vriniti vmesne korake (prevod, filter, prefix, redaction…) brez prepisovanja osnovnega forwarda.

---

## Ključne odločitve

1. **Trigger**: `on_message` listener (avtomatsko). Filter po `source_channel_id`.
2. **Send mehanizem**: `discord.Webhook` v destinacijskem kanalu — ohrani avatar in nick avtorja, tako da forward izgleda kot original. Bot mora imeti permission **Manage Webhooks**.
3. **Pipeline pattern**: seznam `async` callablov (`Stage`). Vsak prejme + vrne `Envelope` (mutable dataclass). Stage lahko spremeni vsebino, doda metadato, ali vrne `None` za "drop".
4. **Konfiguracija**: dict `{source_id: [dest_id, ...]}` — en vir lahko gre na več destinacij.

---

## Arhitektura

```
on_message  ──►  Envelope (text, author, attachments, meta)
                     │
                     ▼
              Stage 1: filter (npr. ignore bots/commands)
                     │
                     ▼
              Stage 2: transform (npr. translate, prefix)
                     │
                     ▼
              Stage 3: redact (npr. odstrani mentions)
                     │
                     ▼
              Sink: pošlji preko Webhook v dest kanal(e)
```

Vsaka faza je **neodvisna funkcija** — nove faze se dodajo z `pipeline.add(my_stage)`, brez sprememb v obstoječem kodu.

---

## Struktura datotek

```
bot/
├── cogs/
│   └── forwarder.py       # Cog z on_message + setup()
└── pipeline/
    ├── __init__.py        # prazen
    ├── envelope.py        # @dataclass Envelope
    ├── pipeline.py        # class Pipeline
    └── stages.py          # gotove faze
```

---

## Koda

### `bot/pipeline/envelope.py`
```python
from dataclasses import dataclass, field
from typing import Optional
import discord

@dataclass
class Envelope:
    content: str
    author_name: str
    author_avatar: Optional[str]
    attachments: list[discord.Attachment] = field(default_factory=list)
    source_message: discord.Message | None = None
    meta: dict = field(default_factory=dict)   # poljubno: lang, score, tags...
```

### `bot/pipeline/pipeline.py`
```python
from typing import Awaitable, Callable, Optional
from .envelope import Envelope

Stage = Callable[[Envelope], Awaitable[Optional[Envelope]]]

class Pipeline:
    def __init__(self) -> None:
        self._stages: list[Stage] = []

    def add(self, stage: Stage) -> "Pipeline":
        self._stages.append(stage)
        return self

    async def run(self, env: Envelope) -> Optional[Envelope]:
        for stage in self._stages:
            env = await stage(env)
            if env is None:           # stage vrne None → drop
                return None
        return env
```

### `bot/pipeline/stages.py`
```python
from .envelope import Envelope

async def filter_bots(env: Envelope) -> Envelope | None:
    if env.source_message and env.source_message.author.bot:
        return None
    return env

async def prefix_author(env: Envelope) -> Envelope:
    env.content = f"[{env.author_name}] {env.content}"
    return env

# Placeholder — pozneje zamenjaj s pravim translate API klicem
async def translate_to_slo(env: Envelope) -> Envelope:
    # env.content = await my_translator.translate(env.content, target="sl")
    env.meta["translated"] = True
    return env
```

### `bot/cogs/forwarder.py`
```python
import discord
from discord.ext import commands
from bot.pipeline.envelope import Envelope
from bot.pipeline.pipeline import Pipeline
from bot.pipeline import stages

# {source_channel_id: [dest_channel_id, ...]}
ROUTES: dict[int, list[int]] = {
    111111111111111111: [222222222222222222],
}

class Forwarder(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.pipeline = (
            Pipeline()
            .add(stages.filter_bots)
            .add(stages.prefix_author)
            # .add(stages.translate_to_slo)   # ← prižgi, ko boš pripravljen
        )
        self._webhook_cache: dict[int, discord.Webhook] = {}

    async def _get_webhook(self, channel: discord.TextChannel) -> discord.Webhook:
        if channel.id in self._webhook_cache:
            return self._webhook_cache[channel.id]
        hooks = await channel.webhooks()
        hook = discord.utils.get(hooks, name="forwarder") \
            or await channel.create_webhook(name="forwarder")
        self._webhook_cache[channel.id] = hook
        return hook

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        dests = ROUTES.get(message.channel.id)
        if not dests or message.webhook_id:   # izogni se zanki
            return

        env = Envelope(
            content=message.content or "",
            author_name=message.author.display_name,
            author_avatar=message.author.display_avatar.url,
            attachments=list(message.attachments),
            source_message=message,
        )
        out = await self.pipeline.run(env)
        if out is None:
            return

        files = [await a.to_file() for a in out.attachments]
        for dest_id in dests:
            channel = self.bot.get_channel(dest_id)
            if not isinstance(channel, discord.TextChannel):
                continue
            hook = await self._get_webhook(channel)
            await hook.send(
                content=out.content or "​",   # zero-width če prazno
                username=out.author_name,
                avatar_url=out.author_avatar,
                files=files,
                allowed_mentions=discord.AllowedMentions.none(),
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Forwarder(bot))
```

---

## Predpogoji

- `intents.message_content = True` na bot instanci **in** v Discord Developer Portal pri botu vklopljen "Message Content Intent".
- Bot ima v destinacijskem kanalu permission **Manage Webhooks**.
- `message.webhook_id` check prepreči neskončno zanko, če bi destinacija slučajno bila tudi vir.

---

## Kako se doda nova faza pozneje

1. Napiši `async def my_stage(env): ... return env` v `stages.py`.
2. Dodaj `.add(stages.my_stage)` v `Forwarder.__init__`.
3. Konec. Nobenega drugega koda ni treba dotikati.

Primeri prihodnjih faz:
- **translate**: kliče DeepL / OpenAI / LibreTranslate, postavi `env.meta["lang"]` in zamenja `env.content`.
- **per-route pipeline**: če različni pari kanalov rabijo različne transformacije, uporabi `dict[int, Pipeline]` namesto enega skupnega.
- **rate limit / dedup**: stage z LRU/TTL kešom, vrne `None` za duplikate.
- **media filter**: počisti `env.attachments` po MIME tipu ali velikosti.
- **redact**: odstrani `@everyone`, povezave, regex matche.

---

## Verifikacija

1. Dodaj 2 testna kanala v isti server, vpiši ID-je v `ROUTES`.
2. Pošlji navadno sporočilo v source → preveri, da pride v dest pod istim avatarjem/nickom.
3. Preveri, da bot sporočila ne forwarda nazaj (webhook_id guard).
4. Pošlji sliko/file → preveri, da attachments pridejo skozi.
5. Vklopi `prefix_author` → potrdi, da se vsebina spreminja v eni točki.
6. Doda placeholder `translate_to_slo` → potrdi, da meta polje pride do destinacije (dodaj log).

---

## Kaj **ni** v scope-u

- Persistenca routes v DB (zaenkrat hardcoded dict; pozneje YAML/JSON config ali slash command).
- Edit/delete propagacija (če source uredi sporočilo, dest ostane star — rabilo bi `on_message_edit` + cache message ID mappinga).
- Cross-server forwarding sicer deluje (`bot.get_channel(id)` ni omejen na guild), ampak bot mora biti v obeh.
