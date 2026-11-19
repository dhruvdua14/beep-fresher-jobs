/*
  Listings page. Plain JavaScript, no build step.

  1. Load data/jobs.json (written by the daily pipeline).
  2. Keep the current search + filters in `state`, mirrored in the URL,
     so any filtered view can be shared as a link.
  3. On every change: filter -> count facets -> render.
*/

const PAGE = 40;                       // rows rendered per "Show more"
const LEVEL_ORDER = ["Internship", "Fresher", "Early career"];
// shown in the Type filter so students know what each level means
const LEVEL_LABEL = { Internship: "Internship", Fresher: "Fresher (0–1 yr)", "Early career": "Early career (up to 2 yrs)" };

// Typing "bangalore" should find "Bengaluru", and so on.
const ALIASES = {
  bangalore: ["bengaluru"], blr: ["bengaluru"], gurgaon: ["gurugram"], ggn: ["gurugram"],
  bombay: ["mumbai"], ncr: ["delhi", "gurugram", "noida"], madras: ["chennai"],
  calcutta: ["kolkata"], trivandrum: ["thiruvananthapuram"], cochin: ["kochi"],
  hyd: ["hyderabad"], wfh: ["remote"], sde: ["software"], swe: ["software"],
  ml: ["ai / ml", "machine learning"], ai: ["ai / ml", " ai "], pm: ["product"],
  internship: ["intern"],
};

const $ = (id) => document.getElementById(id);
const state = { q: "", role: "", city: "", level: "", sort: "new", shown: PAGE };
let JOBS = [];
let TODAY = "";
let HAS_HISTORY = false;

// ------------------------------------------------------------- load

fetch("data/jobs.json", { cache: "no-cache" })
  .then((r) => r.json())
  .then((data) => {
    TODAY = data.updated_at.slice(0, 10);
    JOBS = data.jobs.map((j) => ({
      ...j,
      // one lowercase string per job, so search is a simple .includes()
      hay: " " + [j.title, j.company, j.location, j.role, j.level, ...(j.cities || [])].join(" ").toLowerCase() + " ",
    }));
    $("updated").textContent =
      `Updated ${formatStamp(data.updated_at)} · ${data.count} openings`;
    // "New" means it first appeared in today's run. On the very first run
    // everything is new, so the marker is switched off until there's history.
    HAS_HISTORY = JOBS.some((j) => j.first_seen !== TODAY);
    readURL();
    render();
  })
  .catch(() => {
    $("list").innerHTML = `<li class="empty">Couldn't load today's listings. Try refreshing.</li>`;
  });

// ------------------------------------------------------------- filtering

// Each search word becomes a list of alternatives: "ncr" -> ["delhi","gurugram","noida"].
function terms(q) {
  return q.toLowerCase().trim().split(/\s+/).filter(Boolean)
    .map((t) => ALIASES[t] || [t]);
}

function matches(job, skip) {
  // `skip` lets facet counts ignore their own filter (so "Pune 12" means
  // "12 results if you pick Pune", given all the *other* filters).
  if (skip !== "role" && state.role && job.role !== state.role) return false;
  if (skip !== "city" && state.city && !(job.cities || []).includes(state.city)) return false;
  if (skip !== "level" && state.level && job.level !== state.level) return false;
  // every search word must match (one of its alternatives is enough)
  return terms(state.q).every((alts) => alts.some((w) => job.hay.includes(w)));
}

function results() {
  const out = JOBS.filter((j) => matches(j));
  if (state.sort === "company") out.sort((a, b) => a.company.localeCompare(b.company));
  return out; // otherwise keep the pipeline's order: newest first
}

function countBy(skip, keyFn) {
  const counts = new Map();
  for (const j of JOBS) {
    if (!matches(j, skip)) continue;
    for (const k of keyFn(j)) counts.set(k, (counts.get(k) || 0) + 1);
  }
  return counts;
}

// ------------------------------------------------------------- rendering

function render() {
  const list = results();
  renderFacet("f-level", "level", countBy("level", (j) => [j.level]), LEVEL_ORDER);
  renderFacet("f-role", "role", countBy("role", (j) => [j.role]));
  renderFacet("f-city", "city", countBy("city", (j) => j.cities || []));

  const active = [state.level, state.role, state.city].filter(Boolean);
  $("filtersummary").textContent = active.length ? `Filtered: ${active.join(", ")}` : "Filter by role, city, type";
  $("clear").hidden = !(active.length || state.q);
  $("count").innerHTML = list.length === JOBS.length
    ? `<b>${list.length}</b> openings`
    : `<b>${list.length}</b> of ${JOBS.length} openings`;

  if (!list.length) {
    // If the search finds something once the role/city/type filters are off, say so,
    // so a forgotten filter never looks like "this job doesn't exist".
    const elsewhere = state.q && active.length
      ? JOBS.filter((j) => terms(state.q).every((alts) => alts.some((w) => j.hay.includes(w)))).length : 0;
    $("list").innerHTML = elsewhere
      ? `<li class="empty">No “${esc(state.q)}” in ${esc(active.join(", "))}, but
          ${elsewhere} ${elsewhere === 1 ? "opening matches" : "openings match"} without these filters.
          <button class="linkbtn" onclick="clearFilters()">Show ${elsewhere === 1 ? "it" : "them"}</button>.</li>`
      : `<li class="empty">Nothing matches${state.q ? ` “${esc(state.q)}”` : ""}.
          Try a broader word, or <button class="linkbtn" onclick="clearAll()">clear the filters</button>.</li>`;
    $("more").hidden = true;
    return;
  }
  const words = terms(state.q).flat().map((w) => w.trim());
  $("list").innerHTML = list.slice(0, state.shown).map((j) => row(j, words)).join("");
  $("more").hidden = list.length <= state.shown;
  $("more").textContent = `Show ${Math.min(PAGE, list.length - state.shown)} more`;
}

function row(j, words) {
  const isNew = HAS_HISTORY && j.first_seen === TODAY;
  const date = j.posted_at || j.first_seen;
  // "Other India" is a filter bucket, not a place: show what the employer wrote instead
  const cities = (j.cities && j.cities.length && !j.cities.includes("Other India") ? j.cities
    : [j.location.replace(/, India(, India)?$/, "") || "India"]).join(", ");
  return `<li class="row">
    <div class="date mono">${isNew ? '<span class="new">New</span>' : ""}${formatDay(date)}</div>
    <div>
      <h3><a href="${esc(j.url)}" target="_blank" rel="noopener">${hl(j.title, words)}</a></h3>
      <div class="meta"><span class="co">${hl(j.company, words)}</span><span class="sep">/</span>${esc(cities)}</div>
      <div class="tags mono"><span>${esc(j.role)}</span><span class="lvl-${esc(j.level)}">${esc(j.level)}</span></div>
    </div>
    <a class="apply" href="${esc(j.url)}" target="_blank" rel="noopener">Apply ↗</a>
  </li>`;
}

function renderFacet(elId, key, counts, order) {
  let names = order ? order.filter((n) => counts.has(n) || state[key] === n)
    : [...counts.keys()].sort((a, b) => counts.get(b) - counts.get(a) || a.localeCompare(b));
  if (state[key] && !names.includes(state[key])) names.unshift(state[key]);
  const total = [...JOBS].filter((j) => matches(j, key)).length;
  const item = (value, label, n) =>
    `<li><button type="button" data-key="${key}" data-value="${esc(value)}"
      aria-pressed="${state[key] === value}" ${n === 0 && state[key] !== value ? "disabled" : ""}>
      <span>${esc(label)}</span><span class="n">${n}</span></button></li>`;
  const label = (n) => (key === "level" && LEVEL_LABEL[n]) || (n === "Other India" ? "Other city / not stated" : n);
  $(elId).innerHTML = item("", "All", total) + names.map((n) => item(n, label(n), counts.get(n) || 0)).join("");
}

// ------------------------------------------------------------- events

document.addEventListener("click", (e) => {
  const b = e.target.closest("button[data-key]");
  if (!b) return;
  state[b.dataset.key] = b.dataset.value;
  update();
});

let typing;
$("q").addEventListener("input", (e) => {
  state.q = e.target.value;
  clearTimeout(typing);
  typing = setTimeout(update, 80); // instant, but not on every single keystroke
});
$("sort").addEventListener("change", (e) => { state.sort = e.target.value; update(); });
$("more").addEventListener("click", () => { state.shown += PAGE; render(); });
$("clear").addEventListener("click", clearAll);

// "/" focuses search, Escape clears it
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && document.activeElement !== $("q")) { e.preventDefault(); $("q").focus(); }
  if (e.key === "Escape" && document.activeElement === $("q")) { $("q").value = ""; state.q = ""; update(); }
});

// open the filter panel by default on wide screens
if (matchMedia("(min-width: 900px)").matches) $("filterbox").open = true;

function clearAll() {
  Object.assign(state, { q: "", role: "", city: "", level: "" });
  $("q").value = "";
  update();
}

// keep the search words, drop role / city / type
function clearFilters() {
  Object.assign(state, { role: "", city: "", level: "" });
  update();
}

function update() {
  state.shown = PAGE;
  writeURL();
  render();
}

// ------------------------------------------------------------- URL state

function readURL() {
  const p = new URLSearchParams(location.search);
  for (const k of ["q", "role", "city", "level", "sort"]) if (p.get(k)) state[k] = p.get(k);
  $("q").value = state.q;
  $("sort").value = state.sort;
}

function writeURL() {
  const p = new URLSearchParams();
  for (const k of ["q", "role", "city", "level"]) if (state[k]) p.set(k, state[k]);
  if (state.sort !== "new") p.set("sort", state.sort);
  history.replaceState(null, "", p.toString() ? `?${p}` : location.pathname);
}

// ------------------------------------------------------------- helpers

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Wrap search words in <mark>, escaping everything else.
function hl(text, words) {
  words = words.filter((w) => w.length > 1);
  if (!words.length) return esc(text);
  const re = new RegExp(`(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "ig");
  return String(text).split(re).map((part, i) => (i % 2 ? `<mark>${esc(part)}</mark>` : esc(part))).join("");
}

function formatDay(iso) {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

function formatStamp(iso) {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" }) + " IST";
}
