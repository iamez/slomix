/**
 * Website Diagnostics Module
 * Run comprehensive health checks on the Slomix website
 *
 * Usage in browser console: runDiagnostics()
 */

const DIAGNOSTIC_VERSION = '1.0.0';

/**
 * Test configuration
 */
const TESTS = {
    api: [
        { name: 'API Status', endpoint: '/api/status', required: true },
        { name: 'Stats Overview', endpoint: '/api/stats/overview', required: true },
        { name: 'Leaderboard', endpoint: '/api/stats/leaderboard?limit=5', required: true },
        { name: 'Recent Matches', endpoint: '/api/stats/matches?limit=5', required: true },
        { name: 'Sessions List', endpoint: '/api/sessions?limit=5', required: true },
        { name: 'Live Status', endpoint: '/api/live-status', required: true },
        { name: 'Server Activity', endpoint: '/api/server-activity/history?hours=24', required: false },
        { name: 'Current Season', endpoint: '/api/seasons/current', required: false },
        { name: 'Last Session', endpoint: '/api/stats/last-session', required: false },
        { name: 'Live Session', endpoint: '/api/stats/live-session', required: false },
        { name: 'Records', endpoint: '/api/stats/records', required: false },
        { name: 'Predictions', endpoint: '/api/predictions/recent?limit=3', required: false },
    ],
    dom: [
        { name: 'Navigation', selector: 'nav', required: true },
        { name: 'Home View', selector: '#view-home', required: true },
        { name: 'Sessions View', selector: '#view-sessions', required: true },
        { name: 'Leaderboards View', selector: '#view-leaderboards', required: true },
        { name: 'Server Status Widget', selector: '#live-server-status', required: true },
        { name: 'Voice Status Widget', selector: '#live-voice-status', required: true },
        { name: 'Chart.js Loaded', check: () => typeof Chart !== 'undefined', required: true },
        { name: 'Lucide Icons Loaded', check: () => typeof lucide !== 'undefined', required: true },
    ],
    functions: [
        { name: 'navigateTo', check: () => typeof window.navigateTo === 'function' },
        { name: 'loadPlayerProfile', check: () => typeof window.loadPlayerProfile === 'function' },
        { name: 'loadMatchDetails', check: () => typeof window.loadMatchDetails === 'function' },
        { name: 'toggleServerDetails', check: () => typeof window.toggleServerDetails === 'function' },
        { name: 'toggleSessionGraphs', check: () => typeof window.toggleSessionGraphs === 'function' },
        { name: 'switchGraphTab', check: () => typeof window.switchGraphTab === 'function' },
        { name: 'openCompareModal', check: () => typeof window.openCompareModal === 'function' },
        { name: 'comparePlayers', check: () => typeof window.comparePlayers === 'function' },
    ]
};

/**
 * Styles for console output
 */
const STYLES = {
    header: 'font-size: 16px; font-weight: bold; color: #3b82f6;',
    section: 'font-size: 14px; font-weight: bold; color: #8b5cf6; margin-top: 10px;',
    pass: 'color: #10b981; font-weight: bold;',
    fail: 'color: #ef4444; font-weight: bold;',
    warn: 'color: #f59e0b; font-weight: bold;',
    info: 'color: #64748b;',
};

/**
 * Get API base URL
 */
function getApiBase() {
    // Return empty string for relative URLs — test endpoints already include /api/ prefix
    return '';
}

/**
 * Test a single API endpoint
 */
async function testApiEndpoint(test) {
    const start = performance.now();
    try {
        const response = await fetch(`${getApiBase()}${test.endpoint}`);
        const duration = Math.round(performance.now() - start);

        if (!response.ok) {
            return {
                name: test.name,
                status: 'fail',
                message: `HTTP ${response.status}`,
                duration,
                required: test.required
            };
        }

        const data = await response.json();

        // Check for error in response
        if (data.error) {
            return {
                name: test.name,
                status: 'warn',
                message: data.error,
                duration,
                required: test.required
            };
        }

        // Check for empty data
        const isEmpty = Array.isArray(data) ? data.length === 0 :
                       data.data_points ? data.data_points.length === 0 : false;

        return {
            name: test.name,
            status: isEmpty ? 'warn' : 'pass',
            message: isEmpty ? 'No data' : `OK (${duration}ms)`,
            duration,
            required: test.required,
            dataPreview: JSON.stringify(data).substring(0, 100) + '...'
        };
    } catch (e) {
        return {
            name: test.name,
            status: 'fail',
            message: e.message,
            duration: Math.round(performance.now() - start),
            required: test.required
        };
    }
}

/**
 * Test DOM element presence
 */
function testDomElement(test) {
    if (test.check) {
        const result = test.check();
        return {
            name: test.name,
            status: result ? 'pass' : 'fail',
            message: result ? 'Found' : 'Not found',
            required: test.required
        };
    }

    const element = document.querySelector(test.selector);
    return {
        name: test.name,
        status: element ? 'pass' : 'fail',
        message: element ? 'Found' : `Selector "${test.selector}" not found`,
        required: test.required
    };
}

/**
 * Test function availability
 */
function testFunction(test) {
    const result = test.check();
    return {
        name: test.name,
        status: result ? 'pass' : 'fail',
        message: result ? 'Available' : 'Not available'
    };
}

/**
 * Print results to console
 */
function printResults(category, results) {
    console.log(`%c📋 ${category}`, STYLES.section);

    results.forEach(r => {
        const icon = r.status === 'pass' ? '✅' : r.status === 'warn' ? '⚠️' : '❌';
        const style = r.status === 'pass' ? STYLES.pass : r.status === 'warn' ? STYLES.warn : STYLES.fail;
        const required = r.required === false ? ' (optional)' : '';
        console.log(`  ${icon} %c${r.name}${required}: %c${r.message}`, style, STYLES.info);
    });
}

/**
 * Run all diagnostics
 */
async function runDiagnostics() {
    console.clear();
    console.log('%c🔍 Slomix Website Diagnostics v' + DIAGNOSTIC_VERSION, STYLES.header);
    console.log('%c' + new Date().toLocaleString(), STYLES.info);
    console.log('');

    const results = {
        api: [],
        dom: [],
        functions: [],
        summary: { pass: 0, warn: 0, fail: 0, critical: 0 }
    };

    // Test API endpoints
    console.log('%c🌐 Testing API Endpoints...', STYLES.section);
    for (const test of TESTS.api) {
        const result = await testApiEndpoint(test);
        results.api.push(result);

        // Update summary
        results.summary[result.status]++;
        if (result.status === 'fail' && result.required) {
            results.summary.critical++;
        }
    }
    printResults('API Endpoints', results.api);

    // Test DOM elements
    TESTS.dom.forEach(test => {
        const result = testDomElement(test);
        results.dom.push(result);
        results.summary[result.status]++;
        if (result.status === 'fail' && result.required) {
            results.summary.critical++;
        }
    });
    printResults('DOM Elements & Libraries', results.dom);

    // Test functions
    TESTS.functions.forEach(test => {
        const result = testFunction(test);
        results.functions.push(result);
        results.summary[result.status]++;
    });
    printResults('JavaScript Functions', results.functions);

    // Print summary
    console.log('');
    console.log('%c📊 Summary', STYLES.header);
    console.log(`  %c✅ Passed: ${results.summary.pass}`, STYLES.pass);
    console.log(`  %c⚠️ Warnings: ${results.summary.warn}`, STYLES.warn);
    console.log(`  %c❌ Failed: ${results.summary.fail}`, STYLES.fail);

    if (results.summary.critical > 0) {
        console.log(`  %c🚨 Critical failures: ${results.summary.critical}`, STYLES.fail);
    }

    // Overall status
    console.log('');
    if (results.summary.critical === 0 && results.summary.fail === 0) {
        console.log('%c✨ All systems operational!', 'font-size: 16px; color: #10b981; font-weight: bold;');
    } else if (results.summary.critical === 0) {
        console.log('%c⚠️ Some non-critical issues detected', 'font-size: 16px; color: #f59e0b; font-weight: bold;');
    } else {
        console.log('%c🚨 Critical issues detected - some features may not work', 'font-size: 16px; color: #ef4444; font-weight: bold;');
    }

    console.log('');
    console.log('%cTip: Run specific tests with testApi(), testDom(), testFunctions()', STYLES.info);

    return results;
}

/**
 * Test only API endpoints
 */
async function testApi() {
    console.log('%c🌐 Testing API Endpoints...', STYLES.header);
    const results = [];
    for (const test of TESTS.api) {
        const result = await testApiEndpoint(test);
        results.push(result);
    }
    printResults('API Endpoints', results);
    return results;
}

/**
 * Test only DOM elements
 */
function testDom() {
    console.log('%c🏗️ Testing DOM Elements...', STYLES.header);
    const results = TESTS.dom.map(testDomElement);
    printResults('DOM Elements', results);
    return results;
}

/**
 * Test only functions
 */
function testFunctions() {
    console.log('%c⚡ Testing Functions...', STYLES.header);
    const results = TESTS.functions.map(testFunction);
    printResults('Functions', results);
    return results;
}

/**
 * Test a specific session's graphs
 */
async function testSessionGraphs(date) {
    if (!date) {
        console.log('%c Usage: testSessionGraphs("2026-01-08")', STYLES.info);
        return;
    }

    console.log(`%c🎨 Testing Session Graphs for ${date}...`, STYLES.header);

    try {
        const response = await fetch(`${getApiBase()}/api/sessions/${date}/graphs`);
        const data = await response.json();

        console.log('%c API Response:', STYLES.section);
        console.log('  Players:', data.players?.length || 0);

        if (data.players?.length > 0) {
            console.log('%c First player structure:', STYLES.section);
            const p = data.players[0];
            console.log('  - name:', p.name);
            console.log('  - combat_offense:', p.combat_offense ? '✅' : '❌');
            console.log('  - combat_defense:', p.combat_defense ? '✅' : '❌');
            console.log('  - advanced_metrics:', p.advanced_metrics ? '✅' : '❌');
            console.log('  - playstyle:', p.playstyle ? '✅' : '❌');
            console.log('  - dpm_timeline:', p.dpm_timeline?.length || 0, 'points');
        }

        return data;
    } catch (e) {
        console.error('%c Failed:', STYLES.fail, e.message);
    }
}

/**
 * Run backend diagnostics (database, tables, permissions)
 */
async function testBackend() {
    console.log('%c🔧 Running Backend Diagnostics...', STYLES.header);

    try {
        const response = await fetch(`${getApiBase()}/api/diagnostics`);
        const data = await response.json();

        console.log('%c📊 Backend Status:', STYLES.section);
        const statusStyle = data.status === 'ok' ? STYLES.pass :
                           data.status === 'warning' ? STYLES.warn : STYLES.fail;
        console.log(`  %cOverall: ${data.status.toUpperCase()}`, statusStyle);
        console.log(`  %cDatabase: ${data.database.status}`, data.database.status === 'connected' ? STYLES.pass : STYLES.fail);

        console.log('%c📋 Tables:', STYLES.section);
        data.tables.forEach(t => {
            const icon = t.status === 'ok' ? '✅' : t.status === 'permission_denied' ? '🔒' : '❌';
            const info = t.status === 'ok' ? `${t.row_count.toLocaleString()} rows` : t.error || t.status;
            const required = t.required ? '' : ' (optional)';
            const style = t.status === 'ok' ? STYLES.pass : STYLES.fail;
            console.log(`  ${icon} %c${t.name}${required}: %c${info}`, style, STYLES.info);
        });

        if (data.issues.length > 0) {
            console.log('%c🚨 Issues:', STYLES.section);
            data.issues.forEach(i => console.log(`  %c❌ ${i}`, STYLES.fail));
        }

        if (data.warnings.length > 0) {
            console.log('%c⚠️ Warnings:', STYLES.section);
            data.warnings.forEach(w => console.log(`  %c⚠️ ${w}`, STYLES.warn));
        }

        return data;
    } catch (e) {
        console.error('%c❌ Backend diagnostics failed:', STYLES.fail, e.message);
        return { status: 'error', error: e.message };
    }
}

/**
 * Quick health check - just pass/fail
 */
async function healthCheck() {
    console.log('%c💓 Quick Health Check...', STYLES.header);

    const checks = {
        api: false,
        database: false,
        charts: typeof Chart !== 'undefined',
        icons: typeof lucide !== 'undefined'
    };

    try {
        const status = await fetch(`${getApiBase()}/api/status`);
        checks.api = status.ok;
    } catch (e) { /* ignore */ }

    try {
        const diag = await fetch(`${getApiBase()}/api/diagnostics`);
        const data = await diag.json();
        checks.database = data.database.status === 'connected';
    } catch (e) { /* ignore */ }

    const allGood = Object.values(checks).every(v => v);

    console.log(allGood ? '%c✨ All systems go!' : '%c⚠️ Some issues detected',
                allGood ? STYLES.pass : STYLES.warn);
    console.table(checks);

    return checks;
}

// Expose to window
window.runDiagnostics = runDiagnostics;
window.testApi = testApi;
window.testDom = testDom;
window.testFunctions = testFunctions;
window.testSessionGraphs = testSessionGraphs;
window.testBackend = testBackend;
window.healthCheck = healthCheck;

// Auto-announce availability
console.log('%c🔧 Diagnostics loaded! Commands: runDiagnostics(), healthCheck(), testBackend()', 'color: #8b5cf6; font-weight: bold;');
