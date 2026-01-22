# 🌐 Website Integration Notes

**Date:** 2025-11-28
**Status:** For Future Reference
**Purpose:** Notes on integrating competitive analytics prediction system with Slomix web frontend

---

## 📋 Current State

### Prediction System (Discord Bot)

- ✅ Fully functional prediction engine
- ✅ 12 Discord commands (7 user + 5 admin)
- ✅ 3 database tables (match_predictions, session_results, map_performance)
- ✅ Complete analytics (trends, leaderboards, maps)
- ✅ Real-time prediction generation
- ✅ Accuracy tracking with Brier scores

### Website Frontend (/website/)

- ✅ Modern Tailwind CSS design
- ✅ Glass morphism UI
- ✅ Chart.js for visualizations
- ✅ FastAPI backend
- ✅ Existing views: Home, Dashboard, Matches, Leaderboards
- ✅ API endpoints for stats, seasons, matches
- ✅ Authentication system
- ✅ Database integration

---

## 🔮 Prediction System Features Ready for Web

### Data Available via Database

All prediction data is stored in PostgreSQL and accessible:

```sql
-- match_predictions table (35 columns)
- prediction_time, session_date, format
- team_a/b_guids, team_a/b_discord_ids
- team_a/b_win_probability
- confidence, confidence_score
- h2h_score, form_score, map_score, subs_score
- key_insight, factor details (JSON)
- actual_winner, prediction_correct, prediction_accuracy
- discord_message_id, discord_channel_id
- guid_coverage

-- session_results table (21 columns)
- session_date, gaming_session_id
- team_1/2_guids, team_1/2_names
- format, total_rounds
- team_1/2_score, winning_team
- round_details (JSON)
- session timing, duration
- team statistics
- substitution details

-- map_performance table (13 columns)
- player_guid, map_name
- matches_played, wins, losses, win_rate
- avg_kills, avg_deaths, avg_kd_ratio
- avg_dpm, avg_efficiency
```python

### Analytics Available

1. **Recent Predictions**
   - Last N predictions with full details
   - Filter by status (pending/completed/correct/incorrect)
   - Sortable, paginated

2. **Accuracy Statistics**
   - Overall accuracy rate
   - Confidence-stratified accuracy
   - Recent trends (last 10 predictions)
   - Time-based filtering (7/30/90 days)

3. **Trend Analysis**
   - Daily accuracy over time
   - Week-over-week comparison
   - Best/worst days
   - Improving/declining detection

4. **Player Leaderboards**
   - Most predictable players
   - Most unpredictable players (wildcards)
   - Most active players
   - Minimum 3 matches filter

5. **Map Analysis**
   - Map-specific accuracy
   - Team bias detection (A/B favoritism)
   - Popular maps
   - Balance insights

6. **Personal Stats**
   - Predictions for specific player
   - Win/loss record in predictions
   - Team assignment history

---

## 💡 Future API Endpoints to Add

### Backend Routes (FastAPI)

Add to `/website/backend/routers/api.py`:

```python
# ==================== PREDICTIONS ====================

@router.get("/predictions/recent")
async def get_recent_predictions(
    limit: int = 10,
    status: str = "all",  # all, pending, completed, correct, incorrect
    db: DatabaseAdapter = Depends(get_db)
):
    """Get recent predictions with filtering"""
    pass

@router.get("/predictions/stats")
async def get_prediction_stats(
    days: int = 30,
    db: DatabaseAdapter = Depends(get_db)
):
    """Get accuracy statistics"""
    pass

@router.get("/predictions/trends")
async def get_prediction_trends(
    days: int = 30,
    db: DatabaseAdapter = Depends(get_db)
):
    """Get daily accuracy trends"""
    pass

@router.get("/predictions/leaderboard")
async def get_prediction_leaderboard(
    category: str = "predictable",  # predictable, unpredictable, active
    db: DatabaseAdapter = Depends(get_db)
):
    """Get player predictability leaderboard"""
    pass

@router.get("/predictions/maps")
async def get_map_predictions(
    map_name: str = None,
    db: DatabaseAdapter = Depends(get_db)
):
    """Get map-specific prediction statistics"""
    pass

@router.get("/predictions/{prediction_id}")
async def get_prediction_detail(
    prediction_id: int,
    db: DatabaseAdapter = Depends(get_db)
):
    """Get specific prediction with full details"""
    pass

@router.get("/predictions/player/{discord_id}")
async def get_player_predictions(
    discord_id: int,
    limit: int = 10,
    db: DatabaseAdapter = Depends(get_db)
):
    """Get predictions for specific player"""
    pass
```yaml

---

## 🎨 Frontend Components to Build

### 1. Predictions Dashboard View

**New Section:** `<div id="view-predictions" class="view-section">`

**Components:**

- Live prediction feed (glass cards)
- Accuracy meter (circular progress with Chart.js)
- Recent trends chart (line graph)
- Quick stats (total, accuracy, pending)

### 2. Analytics Page

**Components:**

- Daily accuracy trend chart
- Best/worst day cards
- Week-over-week comparison
- Interactive date range selector
- Export to CSV button

### 3. Leaderboards Tab

**Subtabs:**

- Most Predictable (🥇🥈🥉 medals)
- Wildcards (unpredictable)
- Most Active
- Personal rank highlight

### 4. Map Analysis Section

**Components:**

- Map grid with accuracy badges
- Team bias indicators
- Filter by map
- Balance visualization
- Click for detailed stats

### 5. Prediction Detail Modal

**Triggered by:** Clicking any prediction card

**Shows:**

- Full team rosters with player names
- Factor breakdown (H2H, Form, Map, Subs)
- Confidence explanation
- Actual outcome (if available)
- Accuracy metrics

---

## 🎯 UI/UX Design Patterns

### Prediction Card (Glass Morphism)

```html
<div class="glass-card p-6 rounded-xl hover:border-brand-blue/30 transition-all">
    <!-- Header -->
    <div class="flex justify-between items-center mb-4">
        <div class="flex items-center gap-3">
            <span class="text-lg font-bold">3v3 Match</span>
            <span class="text-xs text-slate-400">2h ago</span>
        </div>
        <span class="px-3 py-1 bg-brand-emerald/20 text-brand-emerald rounded-full text-sm">
            High Confidence
        </span>
    </div>

    <!-- Probability Bars -->
    <div class="space-y-3">
        <div class="flex items-center gap-3">
            <span class="text-brand-blue font-medium w-20">Team A</span>
            <div class="flex-1 h-3 bg-slate-800/50 rounded-full overflow-hidden">
                <div class="h-full bg-gradient-to-r from-brand-blue to-brand-cyan transition-all duration-500"
                     style="width: 65%"></div>
            </div>
            <span class="font-mono text-sm font-bold w-12 text-right">65%</span>
        </div>
        <div class="flex items-center gap-3">
            <span class="text-brand-rose font-medium w-20">Team B</span>
            <div class="flex-1 h-3 bg-slate-800/50 rounded-full overflow-hidden">
                <div class="h-full bg-gradient-to-r from-brand-rose to-brand-amber transition-all duration-500"
                     style="width: 35%"></div>
            </div>
            <span class="font-mono text-sm font-bold w-12 text-right">35%</span>
        </div>
    </div>

    <!-- Key Insight -->
    <div class="mt-4 p-3 bg-slate-800/30 rounded-lg border border-slate-700/50">
        <p class="text-sm text-slate-300 italic">
            💡 Team A has won 4 of last 5 head-to-head matches
        </p>
    </div>

    <!-- Status Badge (if completed) -->
    <div class="mt-4 flex items-center gap-2">
        <span class="px-2 py-1 bg-brand-emerald/20 text-brand-emerald rounded text-xs">
            ✅ Correct (92% accuracy)
        </span>
        <span class="text-xs text-slate-400">Final: 4-2</span>
    </div>
</div>
```text

### Trend Chart (Chart.js)

```javascript
const trendChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: dates,
        datasets: [{
            label: 'Daily Accuracy',
            data: accuracyData,
            borderColor: 'rgb(59, 130, 246)',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            borderWidth: 2,
            tension: 0.4,
            fill: true,
            pointRadius: 4,
            pointHoverRadius: 6,
            pointBackgroundColor: 'rgb(59, 130, 246)',
            pointBorderColor: 'rgb(15, 23, 42)',
            pointBorderWidth: 2
        }]
    },
    options: {
        responsive: true,
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                borderColor: 'rgba(59, 130, 246, 0.3)',
                borderWidth: 1,
                titleColor: 'rgb(59, 130, 246)',
                bodyColor: 'rgb(226, 232, 240)',
                padding: 12,
                displayColors: false
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                max: 100,
                grid: {
                    color: 'rgba(255, 255, 255, 0.05)'
                },
                ticks: {
                    color: 'rgb(148, 163, 184)',
                    callback: value => value + '%'
                }
            },
            x: {
                grid: {
                    color: 'rgba(255, 255, 255, 0.05)'
                },
                ticks: {
                    color: 'rgb(148, 163, 184)'
                }
            }
        }
    }
});
```text

### Accuracy Meter (Circular Progress)

```html
<div class="relative w-48 h-48 mx-auto">
    <!-- Background circle -->
    <svg class="transform -rotate-90 w-48 h-48">
        <circle cx="96" cy="96" r="88"
                stroke="currentColor"
                class="text-slate-800"
                stroke-width="12"
                fill="none" />
        <!-- Progress circle -->
        <circle cx="96" cy="96" r="88"
                stroke="currentColor"
                class="text-brand-emerald transition-all duration-1000"
                stroke-width="12"
                fill="none"
                stroke-dasharray="552.64"
                stroke-dashoffset="165.79"
                stroke-linecap="round" />
    </svg>
    <!-- Center text -->
    <div class="absolute inset-0 flex flex-col items-center justify-center">
        <span class="text-4xl font-bold text-brand-emerald">72%</span>
        <span class="text-sm text-slate-400">Accuracy</span>
    </div>
</div>
```yaml

---

## 📊 Data Flow

```sql

Discord Bot                    PostgreSQL                    Website
    │                              │                             │
    ├─ Team Split Detected         │                             │
    ├─ Generate Prediction ────────┼─> INSERT match_predictions  │
    ├─ Post to Discord             │                             │
    │                              │                             │
    │                              │   <────── GET /api/predictions/recent
    │                              │   ─────> Return JSON        │
    │                              │                             │
    ├─ Match Completes             │                             │
    ├─ Update Outcome ─────────────┼─> UPDATE match_predictions  │
    │                              │         (actual_winner,     │
    │                              │          prediction_correct)│
    │                              │                             │
    │                              │   <────── GET /api/predictions/stats
    │                              │   ─────> Calculate accuracy │

```

---

## 🚀 Implementation Priority

### Phase 1: Basic Display (1-2 hours)

- [ ] Add `/api/predictions/recent` endpoint
- [ ] Create predictions view in frontend
- [ ] Display prediction cards with glass styling
- [ ] Show recent 10 predictions

### Phase 2: Analytics (2-3 hours)

- [ ] Add `/api/predictions/stats` endpoint
- [ ] Create accuracy meter component
- [ ] Add trend chart with Chart.js
- [ ] Show confidence breakdown

### Phase 3: Leaderboards (1-2 hours)

- [ ] Add `/api/predictions/leaderboard` endpoint
- [ ] Create leaderboard view with tabs
- [ ] Medal system (🥇🥈🥉)
- [ ] Filter by category

### Phase 4: Map Analysis (1-2 hours)

- [ ] Add `/api/predictions/maps` endpoint
- [ ] Create map grid view
- [ ] Team bias indicators
- [ ] Click for details

### Phase 5: Real-time Updates (Optional, 3-4 hours)

- [ ] WebSocket integration
- [ ] Live prediction notifications
- [ ] Auto-refresh on new predictions
- [ ] Popup notifications

---

## 🔧 Technical Considerations

### Database Queries

- Use existing DatabaseAdapter pattern
- Leverage parameterized queries ($1, $2, etc.)
- Optimize with proper indexes (already exist)
- Cache frequently accessed data

### Performance

- Paginate results (limit/offset)
- Cache API responses (Redis optional)
- Lazy load charts
- Optimize database queries

### Security

- Require authentication for admin endpoints
- Rate limit API calls
- Validate all inputs
- Sanitize player names

### Responsive Design

- Mobile-first approach
- Touch-friendly cards
- Collapsible sections
- Horizontal scroll for tables

---

## 📝 Notes

- All prediction data is already in PostgreSQL (match_predictions table)
- No changes needed to bot - it continues working independently
- Website reads from same database
- Real-time sync via database polling or WebSockets
- Glass morphism design matches existing website aesthetic
- Chart.js already included in website
- Tailwind CSS provides all styling utilities needed

---

## 🎯 Benefits of Integration

1. **For Users:**
   - Beautiful visual interface for predictions
   - Historical data browsing
   - Personal stats tracking
   - Map insights

2. **For Admins:**
   - Web dashboard for monitoring
   - Easy outcome updates
   - System performance metrics
   - Data export capabilities

3. **For Community:**
   - Transparency in predictions
   - Competitive leaderboards
   - Map balance insights
   - Engagement through gamification

---

**Status:** Ready when you are! All backend data is available, just needs API routes and frontend components.
