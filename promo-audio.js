(function(global) {
    var audio = null, fadeTimer = null, stopTimer = null;
    var TARGET_VOLUME = 0.22, FADE_IN_MS = 700, FADE_OUT_MS = 1500;

    function clearTimers() {
        clearInterval(fadeTimer);
        clearTimeout(stopTimer);
        fadeTimer = stopTimer = null;
    }
    function fade(from, to, duration, done) {
        var started = Date.now();
        clearInterval(fadeTimer);
        fadeTimer = setInterval(function() {
            if (!audio) return;
            var p = Math.min(1, (Date.now() - started) / duration);
            audio.volume = Math.max(0, Math.min(1, from + (to - from) * p));
            if (p >= 1) { clearInterval(fadeTimer); fadeTimer = null; if (done) done(); }
        }, 50);
    }
    function stop() {
        clearTimers();
        if (!audio) return;
        audio.onloadedmetadata = null;
        try { audio.pause(); audio.currentTime = 0; audio.volume = 0; } catch(e) {}
    }
    function play(src, slideSeconds) {
        stop();
        audio = new Audio(src);
        audio.preload = 'auto';
        audio.volume = 0;
        var totalMs = Math.max(4000, (slideSeconds || 35) * 1000);
        var result;
        try { result = audio.play(); } catch(e) { return; }
        if (result && result['catch']) result['catch'](function() { clearTimers(); });
        fade(0, TARGET_VOLUME, FADE_IN_MS);
        function scheduleEnd() {
            var audioMs = isFinite(audio.duration) && audio.duration > 0 ? audio.duration * 1000 : totalMs;
            var fadeAt = Math.min(totalMs, audioMs) - FADE_OUT_MS;
            stopTimer = setTimeout(function() { fade(audio.volume, 0, FADE_OUT_MS, stop); }, Math.max(FADE_IN_MS, fadeAt));
        }
        if (audio.readyState >= 1) scheduleEnd(); else audio.onloadedmetadata = scheduleEnd;
    }
    global.PromoAudio = { play: play, stop: stop };
})(window);
