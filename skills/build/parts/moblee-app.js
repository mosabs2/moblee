/* moblee-app.js - the page's half of server.py.
 *
 * Keeps the server alive while this tab is open (a heartbeat every five
 * seconds), tells it goodbye when the tab closes so it can stop, and gives the
 * page two helpers for the plain files in data/:
 *
 *   const rows = await mobleeApp.load("scores");        // reads data/scores.json
 *   await mobleeApp.save("scores", rows);                // writes it, keeping the previous copy
 *
 * Leave the heartbeat and the goodbye alone: without them the server either
 * never stops or stops under the owner.
 */
(function () {
  const headers = { "X-Requested-By": "moblee-app", "Content-Type": "application/json" };

  function beat() {
    fetch("/api/heartbeat", { method: "POST", headers, body: "{}", keepalive: true }).catch(() => {});
  }
  beat();
  setInterval(beat, 5000);
  window.addEventListener("pagehide", function () {
    if (navigator.sendBeacon) navigator.sendBeacon("/api/leaving", "");
  });

  window.mobleeApp = {
    async load(name) {
      const r = await fetch("/api/data/" + encodeURIComponent(name));
      if (r.status === 404) return null;
      if (!r.ok) throw new Error("could not read " + name);
      return r.json();
    },
    async save(name, value) {
      const r = await fetch("/api/save/" + encodeURIComponent(name), {
        method: "POST", headers, body: JSON.stringify(value),
      });
      if (!r.ok) throw new Error("could not save " + name);
      return r.json();
    },
  };
})();
