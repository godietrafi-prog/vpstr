(function() {
    'use strict';

    var API = 'https://gamma-api.polymarket.com/events/slug/world-cup-winner';
    var MARKET_URL = 'https://polymarket.com/event/world-cup-winner';
    var REFRESH_MS = 30000;

    function yesPrice(market) {
        try {
            var outcomes = JSON.parse(market.outcomes || '[]');
            var prices = JSON.parse(market.outcomePrices || '[]');
            var yes = outcomes.indexOf('Yes');
            return yes >= 0 ? Number(prices[yes]) : NaN;
        } catch (e) { return NaN; }
    }

    function setText(selector, text) {
        var nodes = document.querySelectorAll(selector);
        for (var i = 0; i < nodes.length; i++) nodes[i].textContent = text;
    }

    function render(spain, argentina) {
        var spainPct = spain * 100;
        var argentinaPct = argentina * 100;
        var spainText = spainPct.toFixed(1).replace(/\.0$/, '');
        var argentinaText = argentinaPct.toFixed(1).replace(/\.0$/, '');
        setText('[data-poly-spain]', spainText + '%');
        setText('[data-poly-argentina]', argentinaText + '%');
        setText('[data-poly-spain-cents]', spainText + '¢');
        setText('[data-poly-argentina-cents]', argentinaText + '¢');
        setText('[data-poly-ticker]', 'WHO LIFTS THE TROPHY?  ◆  LIVE POLYMARKET ODDS  ◆  SPAIN ' + spainText + '%  ◆  ARGENTINA ' + argentinaText + '%');
        setText('[data-poly-status]', '● LIVE · UPDATED ' + new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}));
        var bars = document.querySelectorAll('[data-poly-bar]');
        for (var i = 0; i < bars.length; i++) bars[i].style.gridTemplateColumns = spainPct + 'fr ' + argentinaPct + 'fr';
        document.documentElement.classList.add('polymarket-live');
    }

    function update() {
        fetch(API, { cache: 'no-store' })
            .then(function(response) { if (!response.ok) throw new Error('HTTP ' + response.status); return response.json(); })
            .then(function(event) {
                var markets = event.markets || [], spain, argentina;
                for (var i = 0; i < markets.length; i++) {
                    if (markets[i].groupItemTitle === 'Spain') spain = yesPrice(markets[i]);
                    if (markets[i].groupItemTitle === 'Argentina') argentina = yesPrice(markets[i]);
                }
                if (!isFinite(spain) || !isFinite(argentina)) throw new Error('Finalist prices unavailable');
                render(spain, argentina);
            })
            .catch(function() { setText('[data-poly-status]', 'POLYMARKET · LIVE DATA TEMPORARILY UNAVAILABLE'); });
    }

    var links = document.querySelectorAll('[data-poly-link]');
    for (var i = 0; i < links.length; i++) links[i].href = MARKET_URL;
    update();
    setInterval(update, REFRESH_MS);
})();
