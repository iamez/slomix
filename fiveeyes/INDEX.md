# 📑 FIVEEYES Documentation Index

**Quick navigation for the complete documentation suite**

---

## 🎯 Start Here

**New to FIVEEYES?** Read these in order:

1. [📖 README.md](README.md) - Overview and quick start guide
2. [🎯 00_MASTER_PLAN.md](00_MASTER_PLAN.md) - Complete project roadmap
3. Choose your implementation path below

---

## 📚 Implementation Guides

### Phase 1: Synergy Detection (Weeks 1-3)
**[📊 01_PHASE1_SYNERGY_DETECTION.md](01_PHASE1_SYNERGY_DETECTION.md)**

- ✅ Uses existing data only (no server changes)
- ✅ Highest value, lowest risk
- ✅ Recommended for everyone

**What you'll build:**
- `!synergy` - Show player duo chemistry
- `!best_duos` - Top player combinations
- `!team_builder` - Balanced team suggestions

---

### Phase 2: Role Normalization (Weeks 4-5)
**[⚖️ 02_PHASE2_ROLE_NORMALIZATION.md](02_PHASE2_ROLE_NORMALIZATION.md)**

- ✅ Fair comparison across classes
- ✅ Engineers get proper credit
- ✅ No server changes required

**What you'll build:**
- `!leaderboard normalized` - Fair rankings
- `!class_stats` - Performance by class
- `!compare` - Fair player comparison

---

### Phase 3: Proximity Tracking (Weeks 6-8) - OPTIONAL
**[📍 03_PHASE3_PROXIMITY_TRACKING.md](03_PHASE3_PROXIMITY_TRACKING.md)**

- ⚠️ Requires Lua scripting
- ⚠️ Needs server-side changes
- ⚠️ Higher complexity

**What you'll build:**
- Crossfire detection
- Support positioning analysis
- `!teamwork` - Proximity-based metrics

---

## 🔧 Technical References

### Database
**[🗄️ 04_DATABASE_SCHEMA.md](04_DATABASE_SCHEMA.md)**

Complete SQL schemas and migration scripts for:
- `player_synergies` table (Phase 1)
- `player_ratings` table (Phase 2)
- `proximity_events` table (Phase 3)

**Use this when:**
- Setting up new tables
- Understanding data structure
- Verifying database state

---

### API Documentation
**[📚 05_API_REFERENCE.md](05_API_REFERENCE.md)**

Complete reference for:
- All Discord commands (usage & examples)
- Python API methods
- Data structures
- Database queries

**Use this when:**
- Adding new features
- Understanding command syntax
- Debugging issues

---

### Performance Analysis
**[⚡ 06_TECHNICAL_PREDICTIONS.md](06_TECHNICAL_PREDICTIONS.md)**

Technical deep-dive covering:
- Performance benchmarks
- Bottleneck identification
- Optimization strategies
- Scalability analysis

**Use this when:**
- Planning infrastructure
- Troubleshooting performance
- Scaling to more players

---

## 🗺️ Decision Tree

### "Where do I start?"

```
Are you new to this project?
├─ YES → Read README.md then 00_MASTER_PLAN.md
└─ NO  → Jump to phase documents below
```

### "Which phase should I implement?"

```
Do you want player synergy analysis?
├─ YES → Implement Phase 1 (01_PHASE1_SYNERGY_DETECTION.md)
│   │
│   └─ Do you want fair class comparison?
│       ├─ YES → Add Phase 2 (02_PHASE2_ROLE_NORMALIZATION.md)
│       │   │
│       │   └─ Do you want proximity tracking?
│       │       ├─ YES + Have Lua skills → Add Phase 3 (03_PHASE3_PROXIMITY_TRACKING.md)
│       │       └─ NO or No Lua skills → Stop at Phase 2 (recommended)
│       │
│       └─ NO → Stop at Phase 1
│
└─ NO → This project might not be for you
```

### "I need help with..."

```
Database setup
└─ 04_DATABASE_SCHEMA.md

Command syntax
└─ 05_API_REFERENCE.md

Performance issues
└─ 06_TECHNICAL_PREDICTIONS.md

Implementation steps
└─ 01/02/03_PHASE*_*.md (your current phase)

Overall understanding
└─ 00_MASTER_PLAN.md
```

---

## 📋 Checklists

### Before Starting

- [ ] Read README.md
- [ ] Read 00_MASTER_PLAN.md
- [ ] Decide which phases to implement
- [ ] Backup your database
- [ ] Test on a dev environment first

### Phase 1 Checklist

- [ ] Read 01_PHASE1_SYNERGY_DETECTION.md
- [ ] Run database migration (04_DATABASE_SCHEMA.md)
- [ ] Implement synergy algorithm
- [ ] Add Discord commands
- [ ] Test with real data
- [ ] Deploy to production

### Phase 2 Checklist

- [ ] Complete Phase 1 first
- [ ] Read 02_PHASE2_ROLE_NORMALIZATION.md
- [ ] Run database migration
- [ ] Define role weights
- [ ] Update leaderboards
- [ ] Gather community feedback
- [ ] Tune weights

### Phase 3 Checklist (Optional)

- [ ] Complete Phase 1 & 2 first
- [ ] Read 03_PHASE3_PROXIMITY_TRACKING.md
- [ ] Test Lua script locally
- [ ] Monitor server performance
- [ ] Update parser
- [ ] Add proximity commands

---

## 🎯 Quick Reference

### File Structure

```
fiveeyes/
├── README.md                          ← Start here
├── INDEX.md                           ← This file
├── 00_MASTER_PLAN.md                  ← Project overview
├── 01_PHASE1_SYNERGY_DETECTION.md     ← Week 1-3 guide
├── 02_PHASE2_ROLE_NORMALIZATION.md    ← Week 4-5 guide
├── 03_PHASE3_PROXIMITY_TRACKING.md    ← Week 6-8 guide
├── 04_DATABASE_SCHEMA.md              ← SQL reference
├── 05_API_REFERENCE.md                ← Command reference
└── 06_TECHNICAL_PREDICTIONS.md        ← Performance guide
```

### Document Lengths

- README: ~5 min read
- MASTER_PLAN: ~15 min read
- Phase guides: ~30-45 min each
- Technical docs: ~20-30 min each

---

## 📊 Document Status

| Document | Status | Last Updated |
|----------|--------|--------------|
| README.md | ✅ Complete | Oct 6, 2025 |
| 00_MASTER_PLAN.md | ✅ Complete | Oct 6, 2025 |
| 01_PHASE1_SYNERGY_DETECTION.md | ✅ Complete | Oct 6, 2025 |
| 02_PHASE2_ROLE_NORMALIZATION.md | ✅ Complete | Oct 6, 2025 |
| 03_PHASE3_PROXIMITY_TRACKING.md | ✅ Complete | Oct 6, 2025 |
| 04_DATABASE_SCHEMA.md | ✅ Complete | Oct 6, 2025 |
| 05_API_REFERENCE.md | ✅ Complete | Oct 6, 2025 |
| 06_TECHNICAL_PREDICTIONS.md | ✅ Complete | Oct 6, 2025 |

---

## 🔗 External Resources

### Related Documentation

- [AI Agent Master Guide](../docs/AI_AGENT_MASTER_GUIDE.md) - Overall project guide
- [Changelog](../CHANGELOG.md) - Project history
- [Main README](../README.md) - Project overview

### External Links

- [ET:Legacy Official](https://www.etlegacy.com/)
- [ET:Legacy Lua Documentation](https://github.com/etlegacy/etlegacy/wiki/Lua)
- [Discord.py Docs](https://discordpy.readthedocs.io/)
- [TrueSkill Algorithm Paper](https://www.microsoft.com/en-us/research/project/trueskill-ranking-system/)

---

## 💡 Tips for Success

### General

1. **Read documents in order** - Each builds on previous knowledge
2. **Test frequently** - Don't wait until the end
3. **Gather feedback** - Community validation is crucial
4. **Start small** - Phase 1 first, then decide on Phase 2/3

### Phase-Specific

**Phase 1:**
- Validate synergy scores match community perception
- Set minimum game thresholds appropriately
- Test with known good/bad player pairs

**Phase 2:**
- Iterate on role weights with community input
- Compare to subjective opinions
- Don't over-weight any single stat

**Phase 3:**
- Test Lua on dev server first
- Monitor performance closely
- Have rollback plan ready

---

## 🎉 Success Indicators

You'll know you're successful when:

✅ **Phase 1:**
- Community uses `!synergy` regularly
- Synergy scores match reality
- Team suggestions are accurate

✅ **Phase 2:**
- Engineers appear in top rankings
- Community agrees scores are fair
- Class leaderboards are active

✅ **Phase 3:**
- No server lag during matches
- Proximity data reveals insights
- Teamwork scores correlate with play style

---

## 📞 Need Help?

### During Development

1. Check **Troubleshooting** sections in phase docs
2. Review **Technical Predictions** for performance issues
3. Consult **API Reference** for syntax/usage
4. Re-read **Master Plan** for big picture

### Common Issues

- "Where do I start?" → README.md
- "What's the timeline?" → 00_MASTER_PLAN.md
- "How do I implement X?" → Phase-specific guide
- "What's this command do?" → 05_API_REFERENCE.md
- "Is this slow?" → 06_TECHNICAL_PREDICTIONS.md
- "Database error?" → 04_DATABASE_SCHEMA.md

---

## 🚀 Ready to Begin?

**Your roadmap:**

1. ✅ You're here (INDEX.md)
2. → Read [README.md](README.md) (5 min)
3. → Read [00_MASTER_PLAN.md](00_MASTER_PLAN.md) (15 min)
4. → Choose phase and follow guide (varies)
5. → Reference technical docs as needed
6. → Build something amazing! 🎉

---

**Good luck, and have fun building the most advanced ET:Legacy analytics system!** 🚀

---

*Documentation Suite Version: 1.0*  
*Created: October 6, 2025*  
*Status: Complete & Ready for Implementation*
