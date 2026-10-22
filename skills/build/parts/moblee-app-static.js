/* moblee-app-static.js - the page's helper for the copy that lives on the web.
 *
 * On the Mac, moblee-app.js talks to server.py. On the web there is no server:
 * this file stands in for it, so the same page works unchanged. load() reads
 * the plain files publish.py copied into data/; save() cannot write anywhere,
 * so it says so. Nothing here keeps a heartbeat and nothing is sent anywhere.
 */
(function () {
  window.mobleeApp = {
    async load(name) {
      const r = await fetch("data/" + encodeURIComponent(name) + ".json", { cache: "no-store" });
      if (r.status === 404) return null;
      if (!r.ok) throw new Error("could not read " + name);
      return r.json();
    },
    async save() {
      throw new Error("This copy is on the web and cannot save. Changes are made on the Mac, and the web copy is updated from there.");
    },
    onTheWeb: true,
  };
})();
