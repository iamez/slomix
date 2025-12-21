import io

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:
    matplotlib = None
    plt = None


def create_performance_image(top_players, title_date: str):
    """Create a 2x3 performance PNG for the provided top_players.

        top_players: iterable of rows with fields. Example minimal row:
            (player_name, kills, deaths, dpm, time_played_seconds,
             time_dead_seconds, denied)

    Returns: BytesIO buffer containing PNG image.
    """
    if plt is None:
        raise ImportError("matplotlib not available")

    # Accept flexible row shapes: expected row format (at minimum):
    # (name, kills, deaths, dpm, time_played_seconds, time_dead_seconds,
    #  denied, [revives], [gibs])
    player_names = [p[0] for p in top_players]
    kills = [p[1] or 0 for p in top_players]
    deaths = [p[2] or 0 for p in top_players]
    dpm = [p[3] or 0 for p in top_players]
    time_played = [
        (p[4] / 60) if len(p) > 4 and p[4] else 0 for p in top_players
    ]
    time_dead = [
        (p[5] / 60) if len(p) > 5 and p[5] else 0 for p in top_players
    ]
    # optional fields
    revives = [p[7] or 0 if len(p) > 7 else 0 for p in top_players]
    gibs = [p[8] or 0 if len(p) > 8 else 0 for p in top_players]

    # New layout: two main panels side-by-side
    # Make width scale with number of players so labels don't overlap
    n_players = max(1, len(player_names))
    fig_width = max(12, n_players * 0.9)
    fig, axes = plt.subplots(1, 2, figsize=(fig_width, 8))
    fig.suptitle(
        f"Visual Performance Analytics - {title_date}",
        fontsize=18,
        fontweight="bold",
    )

    # Left panel: grouped bars for Kills, Deaths, Gibs and DPM as a line
    ax_left = axes[0]
    x = range(len(player_names))
    width = 0.22

    # Per-item sanity-check for gibs: scale down any gib counts that are
    # wildly larger than the corresponding kills (likely an extra zero).
    scaled_gibs = []
    scaled_any = False
    for idx, g in enumerate(gibs):
        try:
            k = kills[idx] if idx < len(kills) else 0
            s = float(g)
            if k > 0:
                threshold = max(50, k * 5)
            else:
                threshold = 500
            scaled = False
            while s > threshold and s >= 1:
                s = s / 10.0
                scaled = True
            if scaled:
                scaled_any = True
        except Exception:
            s = float(g)
        scaled_gibs.append(int(round(s)))

    b1 = ax_left.bar(
        [i - width for i in x],
        kills,
        width,
        label="Kills",
        color="#57F287",
        alpha=0.9,
    )
    b2 = ax_left.bar(
        x,
        deaths,
        width,
        label="Deaths",
        color="#ED4245",
        alpha=0.9,
    )
    b3 = ax_left.bar(
        [i + width for i in x],
        scaled_gibs,
        width,
        label=("Gibs (scaled)" if scaled_any else "Gibs"),
        color="#ff7f50",
        alpha=0.9,
    )

    # Plot DPM as a line on a secondary axis so it doesn't force bar scaling
    ax_left2 = ax_left.twinx()
    dpm_line, = ax_left2.plot(
        list(x),
        dpm,
        marker="o",
        color="#FEE75C",
        label="DPM",
        linewidth=2,
    )
    ax_left2.set_ylabel("DPM")

    ax_left.set_title("Kills • Deaths • Gibs • DPM", fontweight="bold", fontsize=12)
    ax_left.set_xticks(x)
    ax_left.set_xticklabels(player_names, rotation=35, ha="right", fontsize=10)
    # Combine legends from both axes and place outside to avoid overlap
    h1, l1 = ax_left.get_legend_handles_labels()
    h2, l2 = ax_left2.get_legend_handles_labels()
    ax_left.legend(
        h1 + h2,
        l1 + l2,
        loc="upper left",
        bbox_to_anchor=(1.02, 1),
        fontsize=10,
        frameon=False,
    )
    ax_left.grid(axis="y", alpha=0.15)

    # annotate top values for kills/deaths/gibs and annotate DPM values
    for bars in (b1, b2, b3):
        for bar in bars:
            h = bar.get_height()
            ax_left.text(
                bar.get_x() + bar.get_width() / 2.0,
                h,
                f"{int(h)}",
                ha="center",
                va="bottom",
                fontsize=9,
            )
    for xi, val in enumerate(dpm):
        ax_left2.text(
            xi,
            val,
            f"{val:.0f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    # Right panel: time played, time dead, revives, gibs
    ax_right = axes[1]
    width2 = 0.18
    offsets = [-1.5 * width2, -0.5 * width2, 0.5 * width2]
    # Plot primary bars for time played, time dead, revives
    r1 = ax_right.bar(
        [i + offsets[0] for i in x],
        time_played,
        width2,
        label="Time Played (m)",
        color="#5865F2",
    )
    r2 = ax_right.bar(
        [i + offsets[1] for i in x],
        time_dead,
        width2,
        label="Time Dead (m)",
        color="#EB459E",
    )
    r3 = ax_right.bar(
        [i + offsets[2] for i in x],
        revives,
        width2,
        label="Revives",
        color="#9B59B6",
    )


    ax_right.set_title(
        "Playtime • Time Dead • Revives",
        fontweight="bold",
        fontsize=12,
    )
    ax_right.set_xticks(x)
    ax_right.set_xticklabels(player_names, rotation=35, ha="right", fontsize=10)
    ax_right.legend(loc="upper left", bbox_to_anchor=(1.02, 1), fontsize=10, frameon=False)
    ax_right.grid(axis="y", alpha=0.15)

    # annotate bars lightly for primary bars
    for bars in (r1, r2, r3):
        for bar in bars:
            h = bar.get_height()
            if h:
                val = f"{h:.0f}" if h >= 1 else f"{h:.1f}"
                ax_right.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    h,
                    val,
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )
    # gibs are shown with kills/deaths on the left panel (possibly scaled)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    plt.close()
    return buf


def create_map_performance_image(maps_aggregates, title_date: str):
    """Create a 3-column per-map performance image.

    maps_aggregates: list of dicts, each with at least:
        { 'map': str,
          'kills': int,
          'deaths': int,
          'gibs': int,
          'time_played': float,   # minutes
          'denied': int,
          'time_dead': float,     # minutes
          'damage_given': int,
          'damage_received': int,
          'dpm': float,
        }

    Returns: BytesIO PNG buffer.
    """
    if plt is None:
        raise ImportError("matplotlib not available")

    maps = [m.get('map', f"Map {i+1}") for i, m in enumerate(maps_aggregates)]

    # Extract groups
    kills = [m.get('kills', 0) for m in maps_aggregates]
    deaths = [m.get('deaths', 0) for m in maps_aggregates]
    gibs = [m.get('gibs', 0) for m in maps_aggregates]

    time_played = [m.get('time_played', 0) for m in maps_aggregates]
    denied = [m.get('denied', 0) for m in maps_aggregates]
    time_dead = [m.get('time_dead', 0) for m in maps_aggregates]

    dmg_given = [m.get('damage_given', 0) for m in maps_aggregates]
    dmg_received = [m.get('damage_received', 0) for m in maps_aggregates]
    dpm = [m.get('dpm', 0) for m in maps_aggregates]

    x = range(len(maps))
    # scale width with number of maps so labels remain legible; allow wide
    # figures when many maps are present (user requested all maps shown)
    fig_width = max(14, len(maps) * 1.4)
    fig, axes = plt.subplots(1, 3, figsize=(fig_width, 8))
    fig.suptitle(
        f"Per-Map Performance - {title_date}",
        fontsize=18,
        fontweight="bold",
    )

    # Column 1: kills, deaths, gibs
    ax0 = axes[0]
    width = 0.28
    bars_k = ax0.bar(
        [i - width for i in x],
        kills,
        width,
        label='Kills',
        color='#57F287',
    )
    bars_d = ax0.bar(
        x,
        deaths,
        width,
        label='Deaths',
        color='#ED4245',
    )
    # Plot gibs on a secondary axis as a line to reduce visual dominance
    ax0b = ax0.twinx()
    gib_line, = ax0b.plot(
        list(x),
        gibs,
        marker='o',
        color='#ff7f50',
        label='Gibs',
        linewidth=1.5,
        alpha=0.9,
    )
    ax0.set_title('Kills • Deaths (Gibs as line)', fontsize=12)
    ax0.set_xticks(x)
    # reduce xtick label size when many maps
    map_label_fontsize = max(6, 12 - (len(maps) // 5))
    ax0.set_xticklabels(
        maps, rotation=35, ha='right', fontsize=map_label_fontsize
    )
    # Combine legends and place outside
    h1, l1 = ax0.get_legend_handles_labels()
    h2, l2 = ax0b.get_legend_handles_labels()
    ax0.legend(
        h1 + h2,
        l1 + l2,
        loc='upper left',
        bbox_to_anchor=(1.02, 1),
        fontsize=9,
        frameon=False,
    )
    ax0.grid(axis='y', alpha=0.15)
    # annotate kills/deaths
    for bar in list(bars_k) + list(bars_d):
        h = bar.get_height()
        ax0.text(
            bar.get_x() + bar.get_width() / 2.0,
            h,
            f"{int(h)}",
            ha='center',
            va='bottom',
            fontsize=9,
        )
    # annotate gibs values
    for xi, gv in enumerate(gibs):
        if gv:
            ax0b.text(xi, gv, f"{int(gv)}", ha='left', va='bottom', fontsize=8)

    # Column 2: time played, denied, time dead
    ax1 = axes[1]
    w2 = 0.22
    ax1.bar(
        [i - w2 for i in x],
        time_played,
        w2,
        label='Time Played (m)',
        color='#5865F2',
    )
    ax1.bar(x, denied, w2, label='Denied', color='#9B59B6')
    ax1.bar(
        [i + w2 for i in x],
        time_dead,
        w2,
        label='Time Dead (m)',
        color='#EB459E',
    )
    ax1.set_title('Playtime • Denied • Time Dead', fontsize=12)
    ax1.set_xticks(x)
    ax1.set_xticklabels(
        maps, rotation=35, ha='right', fontsize=map_label_fontsize
    )
    ax1.legend(loc='upper left', bbox_to_anchor=(1.02, 1), fontsize=9, frameon=False)
    ax1.grid(axis='y', alpha=0.15)

    # Column 3: damage given/received and dpm
    ax2 = axes[2]
    w3 = 0.28
    bars_dg = ax2.bar(
        [i - w3 for i in x],
        dmg_given,
        w3,
        label='Damage Given',
        color='#f39c12',
    )
    bars_dr = ax2.bar(
        x,
        dmg_received,
        w3,
        label='Damage Received',
        color='#95a5a6',
    )
    # DPM as a line (keeps damage bars readable)
    ax2b = ax2.twinx()
    dpm_line, = ax2b.plot(
        list(x),
        dpm,
        marker='o',
        color='#FEE75C',
        label='DPM',
        linewidth=1.5,
    )
    ax2.set_title('Damage Given • Received (DPM as line)', fontsize=12)
    ax2.set_xticks(x)
    ax2.set_xticklabels(
        maps, rotation=35, ha='right', fontsize=map_label_fontsize
    )
    h1, l1 = ax2.get_legend_handles_labels()
    h2, l2 = ax2b.get_legend_handles_labels()
    ax2.legend(
        h1 + h2,
        l1 + l2,
        loc='upper left',
        bbox_to_anchor=(1.02, 1),
        fontsize=9,
        frameon=False,
    )
    ax2.grid(axis='y', alpha=0.15)
    # annotate damage bars
    for bar in list(bars_dg) + list(bars_dr):
        h = bar.get_height()
        ax2.text(
            bar.get_x() + bar.get_width() / 2.0,
            h,
            f"{int(h)}",
            ha='center',
            va='bottom',
            fontsize=9,
        )
    # annotate dpm values
    for xi, val in enumerate(dpm):
        ax2b.text(xi, val, f"{val:.0f}", ha='center', va='bottom', fontsize=8)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    return buf


def create_map_performance_images(
    maps_aggregates,
    title_date: str,
    maps_per_image: int = 3,
    per_map_players: dict = None,
    top_n_players: int = 12,
):
    """Create one or more images, each showing up to `maps_per_image` maps.

    Layout: each image contains `maps_per_image` columns (one column per map),
    and three stacked rows of panels per column:
      Row 0: Kills, Deaths, Gibs, DPM
      Row 1: Time Played, Denied, Time Dead, Revives
      Row 2: Damage Given, Damage Received, Team Damage (optional), DPM

    Returns: list of BytesIO PNG buffers (one per image chunk).
    """
    if plt is None:
        raise ImportError("matplotlib not available")

    if not maps_aggregates:
        return []

    # Helper to get safe values
    def gv(d, k):
        return d.get(k, 0) or 0

    buffers = []
    # Chunk maps into groups of maps_per_image
    for start in range(0, len(maps_aggregates), maps_per_image):
        chunk = maps_aggregates[start : start + maps_per_image]
        cols = len(chunk)

    # build arrays per chunk
        names = [m.get("map", f"Map {i+1}") for i, m in enumerate(chunk, start=start)]
        kills = [gv(m, "kills") for m in chunk]
        deaths = [gv(m, "deaths") for m in chunk]
        gibs = [gv(m, "gibs") for m in chunk]

        time_played = [gv(m, "time_played") for m in chunk]
        denied = [gv(m, "denied") for m in chunk]
        time_dead = [gv(m, "time_dead") for m in chunk]
        revives = [gv(m, "revives") for m in chunk]

        dmg_given = [gv(m, "damage_given") for m in chunk]
        dmg_received = [gv(m, "damage_received") for m in chunk]
        team_dmg = [gv(m, "team_damage") for m in chunk]
        dpm = [gv(m, "dpm") for m in chunk]

        # Figure sizing: columns * width, and extra height to fit per-map player charts
        # bottom player panel height scales with number of players (max top_n_players)
        max_players_shown = top_n_players
        player_panel_height = 1.8 if max_players_shown <= 6 else 2.8
        fig_w = max(8, cols * 4)
        fig_h = 9 + player_panel_height
        # We'll create 4 rows: 0=aggregates (kills/deaths/gibs), 1=time metrics (denied/time dead/revives),
        # 2=damage metrics, 3=per-map player charts
        fig, axes = plt.subplots(4, cols, figsize=(fig_w, fig_h))
        fig.suptitle(f"Per-Map Performance - {title_date}", fontsize=16, fontweight="bold")

        if cols == 1:
            axes = axes.reshape(4, 1)

        # Show playtime summary above the charts (per chunk use max or median)
        chunk_playtimes = [float(tp or 0) for tp in time_played]
        session_playtime = int(max(chunk_playtimes)) if chunk_playtimes else 0
        # Put playtime as a centered subtitle
        fig.text(0.5, 0.96, f"Playtime (per player): {session_playtime}m", ha="center", va="center", fontsize=12)

        # Row 0: Kills/Deaths/Gibs + DPM line
        for col_idx in range(cols):
            ax = axes[0, col_idx]
            w = 0.25
            k = kills[col_idx]
            d = deaths[col_idx]
            g = gibs[col_idx]
            bars = ax.bar([0 - w, 0, 0 + w], [k, d, g], width=w, color=["#57F287", "#ED4245", "#ff7f50"], alpha=0.9)
            ax.set_title(names[col_idx], fontsize=12, fontweight="bold")
            ax.set_xticks([])
            ax.grid(axis="y", alpha=0.15)
            ax2 = ax.twinx()
            ax2.plot([0], [dpm[col_idx]], marker="o", color="#FEE75C", label="DPM")
            for bar in bars:
                h = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2.0, h, f"{int(h)}", ha="center", va="bottom", fontsize=9)
            if dpm[col_idx]:
                ax2.text(0, dpm[col_idx], f"{dpm[col_idx]:.0f}", ha="left", va="bottom", fontsize=9)

        # Row 1: Denied / Time Dead / Revives
        for col_idx in range(cols):
            ax = axes[1, col_idx]
            vals = [denied[col_idx], time_dead[col_idx], revives[col_idx]]
            labels = ["Denied", "Time Dead (m)", "Revives"]
            colors = ["#9B59B6", "#EB459E", "#57F287"]
            ax.bar(range(len(vals)), vals, color=colors)
            ax.set_xticks(range(len(vals)))
            ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=9)
            ax.grid(axis="y", alpha=0.12)
            for i_bar, val in enumerate(vals):
                if val:
                    ax.text(i_bar, val, f"{int(val)}", ha="center", va="bottom", fontsize=8)

        # Row 2: Damage given / received / team dmg + DPM
        for col_idx in range(cols):
            ax = axes[2, col_idx]
            w = 0.28
            dg = dmg_given[col_idx]
            dr = dmg_received[col_idx]
            td = team_dmg[col_idx]
            bars = ax.bar([0 - w, 0, 0 + w], [dg, dr, td], width=w, color=["#f39c12", "#95a5a6", "#7f8c8d"])
            ax.grid(axis="y", alpha=0.12)
            ax.set_xticks([])
            ax2 = ax.twinx()
            ax2.plot([0], [dpm[col_idx]], marker="o", color="#FEE75C")
            for bar in bars:
                h = bar.get_height()
                if h:
                    ax.text(bar.get_x() + bar.get_width() / 2.0, h, f"{int(h)}", ha="center", va="bottom", fontsize=9)
            if dpm[col_idx]:
                ax2.text(0, dpm[col_idx], f"{dpm[col_idx]:.0f}", ha="center", va="bottom", fontsize=9)

            # Row 3 (bottom): per-map player performance charts (kills/deaths bars + DPM line)
            if per_map_players:
                map_name = names[col_idx]
                players = per_map_players.get(map_name, [])
                if players:
                    p_rows = players[:top_n_players]
                    p_names = [r[0] for r in p_rows]
                    p_kills = [int(r[1] or 0) for r in p_rows]
                    p_deaths = [int(r[2] or 0) for r in p_rows]
                    p_dpm = [float(r[3] or 0) for r in p_rows]

                    axp = axes[3, col_idx]
                    xp = range(len(p_names))
                    wp = 0.35
                    bp1 = axp.bar([i - wp / 2 for i in xp], p_kills, wp, label="Kills", color="#57F287")
                    bp2 = axp.bar([i + wp / 2 for i in xp], p_deaths, wp, label="Deaths", color="#ED4245")
                    axp.set_xticks(xp)
                    axp.set_xticklabels(p_names, rotation=35, ha="right", fontsize=8)
                    axp.set_title("Players (top {})".format(len(p_names)), fontsize=10)
                    axp.grid(axis="y", alpha=0.12)

                    axp2 = axp.twinx()
                    axp2.plot(list(xp), p_dpm, marker="o", color="#FEE75C", label="DPM", linewidth=1.5)
                    # place combined legend outside the axis to avoid overlap when many players
                    h1, l1 = axp.get_legend_handles_labels()
                    h2, l2 = axp2.get_legend_handles_labels()
                    axp.legend(
                        h1 + h2,
                        l1 + l2,
                        loc="upper left",
                        bbox_to_anchor=(1.02, 1),
                        fontsize=9,
                        frameon=False,
                    )
                    # annotate small values
                    for i_bar, bar in enumerate(list(bp1) + list(bp2)):
                        h = bar.get_height()
                        if h:
                            axp.text(bar.get_x() + bar.get_width() / 2.0, h, f"{int(h)}", ha="center", va="bottom", fontsize=8)
                    for xi, val in enumerate(p_dpm):
                        if val:
                            axp2.text(xi, val, f"{val:.0f}", ha="center", va="bottom", fontsize=7)

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0)
        plt.close()
        buffers.append(buf)

    return buffers
