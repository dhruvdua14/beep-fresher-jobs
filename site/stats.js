/* Numbers page: reads data/stats.json (and data/eval.json if the hand check is done). */

const $ = (id) => document.getElementById(id);
const fmt = (n) => (n ?? 0).toLocaleString("en-IN");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

Promise.all([
  fetch("data/stats.json", { cache: "no-cache" }).then((r) => r.json()),
  fetch("data/eval.json", { cache: "no-cache" }).then((r) => (r.ok ? r.json() : null)).catch(() => null),
]).then(([s, ev]) => {
  const L = s.latest;
  $("updated").textContent = `Last run ${new Date(s.updated_at).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" })} IST`;

  // ---------- at a glance
  const dupes = L.exact_dupes + L.fuzzy_dupes;
  $("glance").innerHTML = [
    figure(fmt(L.published), "openings listed today"),
    figure(fmt(L.fetched), `posts fetched from ${L.boards} job boards`),
    figure(fmt(dupes), "duplicates removed", `${L.exact_dupes} exact, ${L.fuzzy_dupes} fuzzy`),
    figure(ev ? `${ev.summary.both.pct}<small>%</small>` : "—", "of hand-checked posts tagged fully right", ev ? `role and city, n = ${ev.summary.both.checked}` : "hand check pending"),
  ].join("");

  // ---------- funnel
  const steps = [
    ["Fetched", L.fetched], ["Located in India", L.india], ["Entry-level by rules", L.fresher_rules],
    ["After removing duplicates", L.fresher_rules - dupes], ["Confirmed by the LLM", L.published],
  ];
  $("funnel").innerHTML = steps.map(([name, n]) => bar(name, n, L.fetched)).join("");

  // ---------- eval
  if (ev) {
    const e = ev.summary;
    $("evalLead").textContent = `${e.sample_size} posts picked at random (fixed seed). Each tag was pre-checked by Claude against the post's original text, then confirmed by hand. The model gave every one of these posts confidence 0.8 or higher, wrong ones included.`;
    $("eval").innerHTML = [
      figure(`${e.role.pct}<small>%</small>`, "role correct", `${e.role.correct} of ${e.role.checked}`),
      figure(`${e.city.pct}<small>%</small>`, "city correct", `${e.city.correct} of ${e.city.checked}`),
      figure(`${e.level.pct}<small>%</small>`, "fresher / intern level correct", `${e.level.correct} of ${e.level.checked}`),
      figure(`${e.both.pct}<small>%</small>`, "role and city both correct", `${e.both.correct} of ${e.both.checked}`),
    ].join("");
    if (ev.role_confusions.length) {
      $("confusions").innerHTML = `<p class="note">Where the model went wrong on role: ` +
        ev.role_confusions.map(([k, n]) => `${esc(k)} (${n})`).join("; ") + ".</p>";
    }
  } else {
    $("eval").innerHTML = `<p class="note">The hand check hasn't been scored yet.</p>`;
  }

  // ---------- cost
  const c = s.cost;
  const inr = c.usd_per_1000 * s.price.usd_to_inr;
  $("costLead").textContent = `Tagging runs on ${s.model}. Figures use Google's paid-tier price, so they show what this would cost at scale. On the free tier the actual bill is zero.`;
  $("cost").innerHTML = [
    figure(`$${c.usd_per_1000 ?? "—"}`, "per 1,000 posts tagged", `about ₹${inr ? inr.toFixed(2) : "—"}`),
    figure(fmt(c.tokens_per_post), "tokens per post", "input + output, prompt shared by 40 posts"),
    figure(fmt(c.posts_tagged_all_time), "LLM tags made across all runs", `${fmt(c.input_tokens)} in · ${fmt(c.output_tokens)} out`),
    figure(`$${(L.cost_usd).toFixed(4)}`, "cost of today's run", `${L.newly_tagged} new posts, ${L.from_cache} from cache`),
  ].join("");
  $("costNote").textContent = `Price used: $${s.price.input_per_m} per million input tokens, $${s.price.output_per_m} per million output tokens. Token counts come from the API's own usage report on every call.`;

  // ---------- distributions
  const maxRole = s.by_role[0]?.[1] || 1;
  $("byRole").innerHTML = s.by_role.map(([k, n]) => bar(k, n, maxRole)).join("");
  const maxCity = s.by_city[0]?.[1] || 1;
  $("byCity").innerHTML = s.by_city.map(([k, n]) => bar(k === "Other India" ? "Other city / not stated" : k, n, maxCity)).join("");

  // ---------- run log
  $("runs").innerHTML = `<thead><tr><th>Date</th><th>Fetched</th><th>Duplicates</th><th>Listed</th><th>New tagged</th><th>LLM calls</th><th>Cost</th></tr></thead><tbody>` +
    s.history.slice().reverse().map((r) => `<tr><td>${r.date} ${r.time}</td><td>${fmt(r.fetched)}</td><td>${r.exact_dupes + r.fuzzy_dupes}</td><td>${r.published}</td><td>${r.newly_tagged}</td><td>${r.llm_calls}</td><td>$${r.cost_usd.toFixed(4)}</td></tr>`).join("") +
    `</tbody>`;
}).catch(() => { $("updated").textContent = "Couldn't load the numbers."; });

function figure(big, label, sub) {
  return `<div class="figure"><div class="big">${big}</div><div class="label">${label}${sub ? `<span class="mono">${sub}</span>` : ""}</div></div>`;
}

function bar(name, n, max) {
  return `<div class="bar"><span class="name" title="${esc(name)}">${esc(name)}</span>
    <span class="track"><span class="fill" style="display:block;width:${Math.max(0.5, (100 * n) / max)}%"></span></span>
    <span class="val">${fmt(n)}</span></div>`;
}
