/**
 * Frontend Performance Test (Playwright)
 * ========================================
 * Measures real browser metrics when rendering an IMAGE-heavy conversation.
 *
 * Metrics collected:
 *  - LCP (Largest Contentful Paint) — should be < 2.5s
 *  - FPS during scroll (rAF-based measurement)
 *  - DOM node count at 50 / 100 / 150 messages
 *  - JS heap size at 50 / 100 / 150 messages
 *  - E2EE decryption time (sequential for loop in useMessagesQuery.ts)
 *
 * Root cause under test:
 *  MessageList.tsx:332 — validMessages.map() renders ALL messages with no
 *  virtualization. react-window is in package.json but unused.
 *
 * Prerequisites:
 *   npm install -D playwright @playwright/test
 *   npx playwright install chromium
 *
 * Run:
 *   CONV_ID=<uuid> CLIENT_URL=http://localhost:3000 \
 *   AUTH_TOKEN=<token> \
 *   npx playwright test stress/browser/media_render.js --reporter=list
 *
 * Or directly:
 *   node stress/browser/media_render.js
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const CLIENT_URL = process.env.CLIENT_URL || 'http://localhost:3000';
const RESULTS_DIR = path.join(__dirname, '..', 'results');
fs.mkdirSync(RESULTS_DIR, { recursive: true });

// Load test data
const DATA_DIR = path.join(__dirname, '..', 'data');
let CONV_ID, AUTH_TOKEN;

try {
  const convData = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'conversation_ids.json'), 'utf8'));
  CONV_ID = process.env.CONV_ID || convData.group_conversation_id;
} catch (e) {
  CONV_ID = process.env.CONV_ID || 'unknown';
}

try {
  const tokens = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'tokens_array.json'), 'utf8'));
  AUTH_TOKEN = process.env.AUTH_TOKEN || tokens[0];
} catch (e) {
  AUTH_TOKEN = process.env.AUTH_TOKEN || '';
}

// ─── Measurement Helpers ──────────────────────────────────────────────────────

/**
 * Measure FPS using requestAnimationFrame for 3 seconds.
 * Inject into page context to get real browser FPS.
 */
async function measureFPS(page, durationMs = 3000) {
  return await page.evaluate((duration) => {
    return new Promise((resolve) => {
      let frameCount = 0;
      let lastTime = performance.now();
      const frameTimes = [];

      function countFrame(currentTime) {
        frameCount++;
        const delta = currentTime - lastTime;
        if (delta > 0) frameTimes.push(delta);
        lastTime = currentTime;

        if (currentTime - (frameTimes[0] ? performance.now() - duration : 0) < duration) {
          requestAnimationFrame(countFrame);
        }
      }

      requestAnimationFrame(countFrame);

      setTimeout(() => {
        const avgFrameTime = frameTimes.length
          ? frameTimes.reduce((a, b) => a + b, 0) / frameTimes.length
          : 16.67;
        const fps = 1000 / avgFrameTime;
        const minFps = frameTimes.length
          ? 1000 / Math.max(...frameTimes)
          : fps;

        resolve({
          avg_fps: Math.round(fps * 10) / 10,
          min_fps: Math.round(minFps * 10) / 10,
          frame_count: frameCount,
          duration_ms: duration,
        });
      }, duration);
    });
  }, durationMs);
}

/**
 * Count DOM nodes currently in the document.
 */
async function countDOMNodes(page) {
  return await page.evaluate(() => document.querySelectorAll('*').length);
}

/**
 * Get JS heap usage (requires --enable-precise-memory-info in Chrome flags).
 */
async function getHeapSize(page) {
  return await page.evaluate(() => {
    if (window.performance && window.performance.memory) {
      return {
        used_mb: Math.round(window.performance.memory.usedJSHeapSize / 1024 / 1024),
        total_mb: Math.round(window.performance.memory.totalJSHeapSize / 1024 / 1024),
        limit_mb: Math.round(window.performance.memory.jsHeapSizeLimit / 1024 / 1024),
      };
    }
    return { used_mb: -1, total_mb: -1, limit_mb: -1, note: 'memory API unavailable' };
  });
}

/**
 * Get LCP from PerformanceObserver.
 */
async function getLCP(page) {
  return await page.evaluate(() => {
    return new Promise((resolve) => {
      let lcp = 0;
      const observer = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        entries.forEach(e => { if (e.startTime > lcp) lcp = e.startTime; });
      });
      try {
        observer.observe({ entryTypes: ['largest-contentful-paint'] });
      } catch (e) {
        resolve(-1);
        return;
      }
      // Wait 3s max for LCP
      setTimeout(() => {
        observer.disconnect();
        resolve(Math.round(lcp));
      }, 3000);
    });
  });
}

// ─── Main Test ───────────────────────────────────────────────────────────────────

async function runTest() {
  console.log('🎭 Browser Performance Test (Playwright)');
  console.log(`   Client URL: ${CLIENT_URL}`);
  console.log(`   Conversation: ${CONV_ID}`);
  console.log(`   Token: ${AUTH_TOKEN ? AUTH_TOKEN.substring(0, 40) + '...' : 'NOT SET'}`);

  const browser = await chromium.launch({
    headless: true,
    args: [
      '--enable-precise-memory-info',  // Required for performance.memory
      '--js-flags=--expose-gc',
      '--disable-web-security',
      '--no-sandbox',
    ],
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
  });

  const page = await context.newPage();
  const results = {
    timestamp: new Date().toISOString(),
    conv_id: CONV_ID,
    measurements: [],
  };

  // Inject auth token into localStorage before navigating
  await page.addInitScript((token) => {
    localStorage.setItem('auth_token', token);
  }, AUTH_TOKEN);

  // Console output from the app
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      console.warn(`  [browser] ${msg.text()}`);
    }
  });

  try {
    // ── Phase 1: Initial load ──────────────────────────────────────────────────

    console.log('\n1️⃣  Phase 1: Initial conversation load (50 messages)');

    const navStart = Date.now();
    await page.goto(`${CLIENT_URL}/chat/${CONV_ID}`, {
      waitUntil: 'networkidle',
      timeout: 30000,
    });
    const navTime = Date.now() - navStart;

    // Wait for messages to render
    await page.waitForSelector('[data-testid="message-bubble"], .message-bubble, [class*="MessageBubble"]', {
      timeout: 15000,
    }).catch(() => {
      console.warn('  ⚠️  Could not find message elements — check selector');
    });

    const lcp = await getLCP(page);
    const domNodes50 = await countDOMNodes(page);
    const heap50 = await getHeapSize(page);

    // Measure FPS with first batch loaded
    const fps50 = await measureFPS(page, 3000);

    // Count rendered messages
    const msgCount50 = await page.evaluate(() => {
      return document.querySelectorAll('[data-testid="message-bubble"], [class*="message-bubble"], [class*="MessageBubble"]').length;
    });

    console.log(`   Nav time: ${navTime}ms`);
    console.log(`   LCP: ${lcp}ms (target: < 2500ms)`);
    console.log(`   DOM nodes: ${domNodes50} (target: < 8000)`);
    console.log(`   JS heap: ${heap50.used_mb}MB (target: < 60MB)`);
    console.log(`   FPS avg: ${fps50.avg_fps} | min: ${fps50.min_fps} (target: > 50fps)`);
    console.log(`   Messages rendered: ${msgCount50}`);

    results.measurements.push({
      phase: '50_messages',
      message_count: msgCount50,
      nav_time_ms: navTime,
      lcp_ms: lcp,
      dom_nodes: domNodes50,
      heap_mb: heap50.used_mb,
      fps: fps50,
    });

    // ── Phase 2: Load older messages (50 → 100) ───────────────────────────────

    console.log('\n2️⃣  Phase 2: Load older messages (50 → 100)');

    const scrollStart = Date.now();

    // Find and click "Load more" button or scroll to trigger infinite scroll
    const loadMoreBtn = await page.$('[data-testid="load-more"], button:has-text("Load more"), button:has-text("Load older")');
    if (loadMoreBtn) {
      await loadMoreBtn.click();
    } else {
      // Scroll to top to trigger infinite scroll
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.keyboard.press('Home');
    }

    // Wait for new messages to load
    await page.waitForTimeout(3000);

    const scrollTime = Date.now() - scrollStart;
    const domNodes100 = await countDOMNodes(page);
    const heap100 = await getHeapSize(page);
    const fps100 = await measureFPS(page, 3000);
    const msgCount100 = await page.evaluate(() =>
      document.querySelectorAll('[data-testid="message-bubble"], [class*="message-bubble"], [class*="MessageBubble"]').length
    );

    console.log(`   Load time: ${scrollTime}ms`);
    console.log(`   DOM nodes: ${domNodes100} (was: ${domNodes50})`);
    console.log(`   JS heap: ${heap100.used_mb}MB (was: ${heap50.used_mb}MB)`);
    console.log(`   FPS avg: ${fps100.avg_fps} | min: ${fps100.min_fps}`);
    console.log(`   Messages rendered: ${msgCount100}`);

    results.measurements.push({
      phase: '100_messages',
      message_count: msgCount100,
      load_time_ms: scrollTime,
      dom_nodes: domNodes100,
      heap_mb: heap100.used_mb,
      fps: fps100,
    });

    // ── Phase 3: Load even older (100 → 150) ─────────────────────────────────

    console.log('\n3️⃣  Phase 3: Load older messages (100 → 150)');

    const scroll2Start = Date.now();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.keyboard.press('Home');
    await page.waitForTimeout(4000);

    const scroll2Time = Date.now() - scroll2Start;
    const domNodes150 = await countDOMNodes(page);
    const heap150 = await getHeapSize(page);
    const fps150 = await measureFPS(page, 3000);
    const msgCount150 = await page.evaluate(() =>
      document.querySelectorAll('[data-testid="message-bubble"], [class*="message-bubble"], [class*="MessageBubble"]').length
    );

    console.log(`   Load time: ${scroll2Time}ms`);
    console.log(`   DOM nodes: ${domNodes150} (was: ${domNodes100})`);
    console.log(`   JS heap: ${heap150.used_mb}MB (was: ${heap100.used_mb}MB)`);
    console.log(`   FPS avg: ${fps150.avg_fps} | min: ${fps150.min_fps}`);
    console.log(`   Messages rendered: ${msgCount150}`);

    results.measurements.push({
      phase: '150_messages',
      message_count: msgCount150,
      load_time_ms: scroll2Time,
      dom_nodes: domNodes150,
      heap_mb: heap150.used_mb,
      fps: fps150,
    });

    // ── Scroll performance test ────────────────────────────────────────────────

    console.log('\n🖱️  Scroll Performance Test');

    // Start FPS measurement
    const scrollFpsPromise = measureFPS(page, 5000);

    // Perform rapid scrolling
    for (let i = 0; i < 20; i++) {
      await page.evaluate((i) => {
        window.scrollBy(0, i % 2 === 0 ? 500 : -500);
      }, i);
      await page.waitForTimeout(100);
    }

    const scrollFps = await scrollFpsPromise;
    console.log(`   Scroll FPS avg: ${scrollFps.avg_fps} | min: ${scrollFps.min_fps}`);

    results.scroll_fps = scrollFps;

    // ── E2EE Decryption timing ─────────────────────────────────────────────────

    console.log('\n🔐 E2EE Decryption Timing');
    const decryptionTime = await page.evaluate(() => {
      // Check for any decryption timing metrics exposed by the app
      if (window.__decryptionMetrics) {
        return window.__decryptionMetrics;
      }
      // Fallback: look for console markers
      return { note: 'No decryption metrics exposed. Add window.__decryptionMetrics in useMessagesQuery.ts' };
    });
    console.log(`   ${JSON.stringify(decryptionTime)}`);
    results.decryption = decryptionTime;

  } catch (err) {
    console.error('❌ Test error:', err.message);
    results.error = err.message;
  } finally {
    await browser.close();
  }

  // ── Verdicts ──────────────────────────────────────────────────────────────────

  console.log('\n' + '═'.repeat(50));
  console.log('📊 BROWSER PERFORMANCE RESULTS');
  console.log('═'.repeat(50));

  const targets = {
    lcp_ms: 2500,
    dom_nodes_50: 8000,
    dom_nodes_150: 20000,
    heap_mb_50: 60,
    heap_mb_150: 150,
    fps_50: 50,
    fps_150: 20,
  };

  if (results.measurements.length > 0) {
    const m50 = results.measurements[0];
    const m150 = results.measurements[results.measurements.length - 1];

    console.log('\nPhase 1 (50 messages):');
    printVerdict('LCP', m50.lcp_ms, targets.lcp_ms, 'ms', 'lower');
    printVerdict('DOM nodes', m50.dom_nodes, targets.dom_nodes_50, '', 'lower');
    printVerdict('JS heap', m50.heap_mb, targets.heap_mb_50, 'MB', 'lower');
    printVerdict('FPS', m50.fps?.avg_fps, targets.fps_50, 'fps', 'higher');

    if (m150) {
      console.log(`\nPhase 3 (${m150.message_count || 150} messages):`);
      printVerdict('DOM nodes', m150.dom_nodes, targets.dom_nodes_150, '', 'lower');
      printVerdict('JS heap', m150.heap_mb, targets.heap_mb_150, 'MB', 'lower');
      printVerdict('FPS', m150.fps?.avg_fps, targets.fps_150, 'fps', 'higher');
    }
  }

  // Write results
  const resultsFile = path.join(RESULTS_DIR, `browser_${Date.now()}.json`);
  fs.writeFileSync(resultsFile, JSON.stringify(results, null, 2));
  console.log(`\n💾 Results saved to: ${resultsFile}`);

  return results;
}

function printVerdict(name, value, threshold, unit, direction) {
  if (value == null || value < 0) {
    console.log(`  ${name}: N/A`);
    return;
  }
  const ok = direction === 'lower' ? value <= threshold : value >= threshold;
  const icon = ok ? '✅' : '❌';
  console.log(`  ${icon} ${name}: ${value}${unit} (target: ${direction === 'lower' ? '<' : '>'} ${threshold}${unit})`);
}

// ─── Entry Point ─────────────────────────────────────────────────────────────────

runTest().catch(console.error);
