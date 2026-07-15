(function(global) {
    var audio = null, fadeTimer = null, stopTimer = null, retryTimer = null;
    var preloaders = {}, generation = 0;
    var TARGET_VOLUME = 0.22, FADE_IN_MS = 700, FADE_OUT_MS = 1500;

    function clearTimers() {
        clearInterval(fadeTimer);
        clearTimeout(stopTimer);
        clearTimeout(retryTimer);
        fadeTimer = stopTimer = retryTimer = null;
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
        generation++;
        clearTimers();
        if (!audio) return;
        audio.onloadedmetadata = null;
        try { audio.pause(); audio.currentTime = 0; audio.volume = 0; } catch(e) {}
    }
    function preload(src) {
        if (!src || preloaders[src]) return;
        var player = new Audio();
        player.preload = 'auto';
        player.src = src;
        player.load();
        preloaders[src] = player;
    }
    function play(src, slideSeconds) {
        stop();
        audio = preloaders[src] || new Audio(src);
        preloaders[src] = audio;
        audio.preload = 'auto';
        audio.volume = 0;
        audio.currentTime = 0;
        var playGeneration = generation;
        var totalMs = Math.max(4000, (slideSeconds || 35) * 1000);
        var attempts = 0, started = false;
        function scheduleEnd() {
            var audioMs = isFinite(audio.duration) && audio.duration > 0 ? audio.duration * 1000 : totalMs;
            var fadeAt = Math.min(totalMs, audioMs) - FADE_OUT_MS;
            stopTimer = setTimeout(function() { fade(audio.volume, 0, FADE_OUT_MS, stop); }, Math.max(FADE_IN_MS, fadeAt));
        }
        function attemptPlay() {
            if (started || playGeneration !== generation || !audio) return;
            attempts++;
            var result;
            try { result = audio.play(); } catch(e) { result = null; }
            if (result && result['then']) {
                result.then(function() {
                    if (playGeneration !== generation) return;
                    started = true;
                    fade(0, TARGET_VOLUME, FADE_IN_MS);
                    if (audio.readyState >= 1) scheduleEnd(); else audio.onloadedmetadata = scheduleEnd;
                })['catch'](function() {
                    if (attempts < 3 && playGeneration === generation)
                        retryTimer = setTimeout(attemptPlay, attempts * 1200);
                });
            } else if (attempts < 3) {
                retryTimer = setTimeout(attemptPlay, attempts * 1200);
            }
        }
        attemptPlay();
    }
    global.PromoAudio = { play: play, stop: stop, preload: preload };
})(window);
