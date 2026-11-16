// Exercise the shipped browser code, including the asynchronous rerun handler.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/main.js', 'utf8');

async function check() {
    let loaded, clicked, response, destination, sent, confirmation, networkError;
    const storage = new Map();
    const modeSelector = {value: 'inventory'};
    const toasts = [];
    const button = {
        textContent: 'Re-run', getAttribute: () => 'sample.yml',
        addEventListener: (event, handler) => { clicked = handler; }
    };
    const context = {
        document: {
            addEventListener: (event, handler) => { loaded = handler; },
            querySelector: () => null,
            querySelectorAll: selector => selector === '.history-rerun-btn' ? [button] : [],
            getElementById: id => id === 'history-execution-mode' ? modeSelector : null,
            documentElement: {classList: {contains: () => false}}
        },
        confirm: message => { confirmation = message; return true; },
        sessionStorage: {
            getItem: key => storage.get(key),
            setItem: (key, value) => storage.set(key, value),
            removeItem: key => storage.delete(key)
        },
        fetch: async (url, options) => {
            sent = {url, ...options};
            if (networkError) throw networkError;
            return {ok: !response.error, status: response.error ? 503 : 202, json: async () => response};
        },
        location: {assign: url => { destination = url; }},
        setTimeout: () => {},
    };
    context.window = context;
    vm.createContext(context);
    vm.runInContext(source, context);
    context.showToast = (message, type) => toasts.push({message, type});
    loaded();
    for (const line of [
        'node : ok=2 changed=0 unreachable=0 failed=1',
        'node : ok=2 changed=0 unreachable=1 failed=0',
        'PLAY RECAP: node : ok=2 failed=1',
        'fatal: [node]: FAILED! <script>alert(1)</script>'
    ]) {
        const html = context.colorizeAnsibleOutput(line);
        assert.ok(html.startsWith('<span class="ap-out-fatal">'), html);
        assert.ok(!html.includes('<script>'));
    }
    for (const state of ['failed', 'launch_error', 'blocked', 'timed_out', 'canceled', 'interrupted', 'uncertain', 'unknown']) {
        const view = context.jobPresentation({state, output: 'ok=9 failed=0'});
        assert.notEqual(view.tone, 'success');
        assert.notEqual(view.toast, 'success');
        assert.equal(view.active, false);
    }
    assert.equal(context.jobPresentation({state: 'succeeded'}).toast, 'success');
    for (const state of ['queued', 'failed', 'succeeded']) {
        response = {url: '/jobs/real-job', state};
        destination = null;
        clicked();
        await new Promise(setImmediate);
        assert.equal(destination, '/jobs/real-job');
        assert.notEqual(toasts.at(-1).type, 'success');
    }
    response = {error: 'The queue is full'};
    clicked();
    await new Promise(setImmediate);
    assert.equal(toasts.at(-1).type, 'error');
    assert.equal(button.disabled, false);
    // Re-runs require an explicit Local selection and retain the submission
    // identity after network or server failure, even if the job finished meanwhile.
    modeSelector.value = 'local';
    networkError = new Error('Response lost');
    clicked();
    await new Promise(setImmediate);
    const retryKey = sent.headers['Idempotency-Key'];
    assert.ok(retryKey);
    assert.ok(confirmation.includes('this control node'));
    assert.ok(sent.body.includes('execution_mode=local'));
    assert.equal(storage.get('pending-run:local:sample.yml'), retryKey);
    networkError = null;
    response = {error: 'Temporary server error'};
    clicked();
    await new Promise(setImmediate);
    assert.equal(sent.headers['Idempotency-Key'], retryKey);
    assert.equal(storage.get('pending-run:local:sample.yml'), retryKey);
    response = {url: '/jobs/original-job', state: 'failed'};
    clicked();
    await new Promise(setImmediate);
    assert.equal(sent.headers['Idempotency-Key'], retryKey);
    assert.equal(destination, '/jobs/original-job');
    assert.equal(storage.has('pending-run:local:sample.yml'), false);
    assert.notEqual(toasts.at(-1).type, 'success');
    modeSelector.value = 'inventory';
    clicked();
    await new Promise(setImmediate);
    assert.ok(confirmation.includes('configured inventory'));
    assert.ok(sent.body.includes('execution_mode=inventory'));
    response = {error: 'Inventory missing', repair: {url: '/settings/', label: 'Repair inventory'}};
    const blocked = await context.submitPlaybook('sample.yml', 'inventory', 'csrf');
    assert.equal(blocked.repair.url, '/settings/');
    // Polling renders the actual terminal result, timings, and toast tone.
    for (const state of ['failed', 'launch_error', 'timed_out', 'canceled', 'interrupted', 'succeeded']) {
        const elements = {};
        for (const id of ['job-state', 'job-started', 'job-finished', 'job-duration', 'job-exit', 'job-output', 'job-review']) {
            elements[id] = {};
        }
        elements['job-detail'] = {dataset: {statusUrl: '/jobs/test/status'}};
        const cancelButton = {};
        elements['job-cancel'] = {querySelector: () => cancelButton, addEventListener: () => {}};
        let initialize;
        const messages = [];
        const page = {
            document: {
                addEventListener: (event, handler) => { initialize = handler; },
                getElementById: id => elements[id] || null,
                querySelector: () => null, querySelectorAll: () => [],
                documentElement: {classList: {contains: () => false}}
            },
            fetch: async () => ({ok: true, json: async () => ({state, playbook: 'test.yml',
                exit_code: state === 'succeeded' ? 0 : 2, started_at: 'start', finished_at: 'end',
                duration: 1.25, needs_review: state === 'interrupted', output: 'ok=1 failed=0'})}),
            setTimeout: () => {}
        };
        page.window = page;
        vm.createContext(page);
        vm.runInContext(source, page);
        page.showToast = (message, type) => messages.push({message, type});
        initialize();
        await new Promise(setImmediate);
        assert.equal(elements['job-state'].className === 'badge badge-success', state === 'succeeded');
        assert.equal(messages[0].type === 'success', state === 'succeeded');
        assert.equal(elements['job-duration'].textContent, '1.25 s');
        assert.equal(elements['job-started'].textContent, 'start');
        assert.equal(elements['job-finished'].textContent, 'end');
        assert.equal(elements['job-review'].hidden, state !== 'interrupted');
        assert.equal(elements['job-cancel'].hidden, true);
    }

}
check().catch(error => { console.error(error); process.exitCode = 1; });
