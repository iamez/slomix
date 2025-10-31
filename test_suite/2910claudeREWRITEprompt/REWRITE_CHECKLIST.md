# ✅ Rewrite Request Checklist

Before submitting your rewrite request, make sure you have:

## 1. Fill in the Prompt Template

Open `REWRITE_PROMPT.md` and replace:
- [ ] `[YOUR_GITHUB_URL_HERE]` with your actual GitHub repo URL
- [ ] Add any additional requirements specific to your setup

## 2. Gather Required Files

Make sure these are accessible (in repo or ready to share):
- [ ] `ultimate_bot_FINAL.py` (your current working bot)
- [ ] `community_stats_parser.py` (from your repo)
- [ ] `tools/stopwatch_scoring.py` (from your repo)
- [ ] Sample stats files: `2025-10-23-*.txt`
- [ ] `c0rnp0rn7.lua` (the Lua stats generator)
- [ ] `.env.example` (sanitized environment variables example)

## 3. Document Current State

Helpful info to include:
- [ ] Which commands currently work perfectly
- [ ] Which commands have issues
- [ ] Any custom modifications you've made
- [ ] Server setup details (OS, Python version, etc.)

## 4. Specify Priorities

Think about what's most important:
- [ ] Must-have features (what can't break)
- [ ] Nice-to-have improvements
- [ ] Features you don't use (can be removed)

## 5. Have Context Ready

Be prepared to answer:
- [ ] How many players use this bot?
- [ ] How often are games played?
- [ ] Are there any performance issues?
- [ ] Any specific pain points with current bot?

## 6. Test Environment

Before requesting rewrite, verify:
- [ ] You have a backup of current bot
- [ ] You have a test environment to deploy new bot
- [ ] Database is backed up
- [ ] You can rollback if needed

---

## Quick Start Template

Here's a quick message you can use with the prompt:

```
Hi! I need help rewriting my ET:Legacy Discord bot for cleaner code and better maintainability.

**GitHub:** [your-repo-url]

**Context:**
- Bot monitors ET:Legacy game servers and tracks player stats
- Current version works but has technical debt from many iterations
- Recent fixes were applied as patches (alias tracking, !stats, !link)
- Need a clean rewrite with all fixes properly integrated

**Priority Issues:**
1. Automatic alias tracking (player_aliases table) - CRITICAL
2. !stats command working properly
3. !link command working properly  
4. New !list_guids command for admin helpers
5. Clean code architecture for future maintenance

**Files Provided:**
- Full prompt with requirements: REWRITE_PROMPT.md
- Current bot: ultimate_bot_FINAL.py
- GitHub repo: [link]
- All necessary dependencies and parsers

Please review REWRITE_PROMPT.md for complete requirements and create a production-ready v2! 🚀
```

---

## After You Get The Rewrite

- [ ] Review the new code
- [ ] Test in dev environment first
- [ ] Run backfill_aliases.py on production DB
- [ ] Deploy to production
- [ ] Test all commands
- [ ] Monitor logs for issues

---

## Pro Tips

1. **Be specific about what works:** "!leaderboard works perfectly, don't change it" helps preserve good code

2. **Share error logs if available:** Any errors or warnings from current bot help understand issues

3. **Mention your skill level:** "I'm not a Python expert" helps get more detailed explanations

4. **Ask for migration guide:** Request step-by-step deployment instructions

5. **Request documentation:** Ask for inline comments and README updates

---

## Quick GitHub Repo Checklist

Make sure your repo has:
- [ ] `ultimate_bot_FINAL.py` (or current bot file)
- [ ] `community_stats_parser.py`
- [ ] `tools/stopwatch_scoring.py`
- [ ] Sample stats files (in `project/` or similar)
- [ ] `c0rnp0rn7.lua` (optional, for reference)
- [ ] `.env.example` (sanitized config template)
- [ ] `requirements.txt` (Python dependencies)
- [ ] Basic README explaining what the bot does

---

**You're all set! Submit the rewrite request with confidence! 🎯**
