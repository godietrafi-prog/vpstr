(function(global) {
    var audio = null;
    var fadeInTimer = null;
    var fadeOutTimer = null;
    var stopTimer = null;
    var TARGET_VOLUME = 0.30;
    var FADE_IN_MS = 1500;
    var FADE_OUT_MS = 2000;

    function clearTimers() {
        clearInterval(fadeInTimer);
        clearInterval(fadeOutTimer);
        clearTimeout(stopTimer);
        fadeInTimer = fadeOutTimer = stopTimer = null;
    }

    function getAudio() {
        if (audio) return audio;
        audio = new Audio('media/audio/happy-birthday.mp3');
        audio.preload = 'auto';
        audio.volume = 0;
        audio.addEventListener('ended', stop);
        return audio;
    }

    function fade(from, to, duration, done) {
        var player = getAudio();
        var started = Date.now();
        var timer = setInterval(function() {
            var progress = Math.min(1, (Date.now() - started) / duration);
            player.volume = Math.max(0, Math.min(1, from + (to - from) * progress));
            if (progress >= 1) {
                clearInterval(timer);
                if (done) done();
            }
        }, 50);
        return timer;
    }

    function stop() {
        clearTimers();
        if (!audio) return;
        audio.onloadedmetadata = null;
        try {
            audio.pause();
            audio.currentTime = 0;
            audio.volume = 0;
        } catch(e) {}
    }

    function play(slideSeconds) {
        stop();
        var player = getAudio();
        var totalMs = Math.max(5000, (slideSeconds || 30) * 1000);
        player.currentTime = 0;
        player.volume = 0;
        var playResult;
        try { playResult = player.play(); } catch(e) { return; }
        if (playResult && playResult['then']) {
            playResult['catch'](function() {
                clearTimers();
            });
        }
        fadeInTimer = fade(0, TARGET_VOLUME, FADE_IN_MS);
        function scheduleFadeOut() {
            clearTimeout(stopTimer);
            var audioMs = isFinite(player.duration) && player.duration > 0 ? player.duration * 1000 : totalMs;
            var fadeAt = Math.min(totalMs, audioMs) - FADE_OUT_MS;
            stopTimer = setTimeout(function() {
                clearInterval(fadeInTimer);
                fadeOutTimer = fade(player.volume, 0, FADE_OUT_MS, stop);
            }, Math.max(FADE_IN_MS, fadeAt));
        }
        if (player.readyState >= 1) scheduleFadeOut();
        else player.onloadedmetadata = scheduleFadeOut;
    }

    global.BirthdayAudio = { play: play, stop: stop };
})(window);
