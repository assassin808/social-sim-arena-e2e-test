// Runs site/index.html's own script against a real data.json and renders the
// question page and the single-forecast page for each answer shape. Exits
// non-zero with the reason when a scored profile or ranking question wears the
// number template (Error / CRPS columns, "no number forecasts"), or when the
// two pages disagree about a forecast's score.
//
// The pipeline marks a scored profile or ranking round resolved in
// `refresh.attach_round_scores`; a data.json built before that change still
// carries them as awaiting_resolution, so the state is derived here from the
// boards the same way, and the test is about the template either way.
const fs = require('fs');
const path = require('path');
const {installGlobals} = require('./dom_stub.js');

const root = path.resolve(__dirname, '..', '..');
const dataPath = process.argv[2] || path.join(root, 'site', 'data.json');
const html = fs.readFileSync(path.join(root, 'site', 'index.html'), 'utf8');
const script = (html.match(/<script>([\s\S]*?)<\/script>/g) || [])
  .map(b => b.replace(/^<script>/, '').replace(/<\/script>$/, '')).join('\n');

const {els} = installGlobals();
const data = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
const problems = [];

// Mirror of refresh.attach_round_scores, for a payload that predates it.
const byId = Object.fromEntries((data.rounds || []).map(r => [r.round_id, r]));
for (const [board, keys] of [[data.profile, ['energy', 'skill']], [data.ranking, ['loss', 'skill']]]) {
  for (const pr of ((board || {}).rounds || [])) {
    const r = byId[pr.round_id];
    if (!r) continue;
    r.scores = Object.fromEntries((pr.entries || []).map(e => [e.entrant,
      Object.fromEntries(keys.filter(k => k in e).map(k => [k, e[k]]))]));
    r.status = 'resolved';
    r.resolution = Object.assign({}, r.resolution || {}, pr.resolution || {}, {outcome: pr.outcome});
    if (Array.isArray(pr.outcome)) r.resolution.items = pr.outcome.slice();
  }
}

eval(script);
render(data);

const scoredProfile = ((data.profile || {}).rounds || [])[0];
const scoredRanking = ((data.ranking || {}).rounds || [])[0];
const numberRound = (data.rounds || []).find(r =>
  (r.target_type || 'continuous_normal') === 'continuous_normal' && r.status === 'resolved'
  && r.scores && r.scores.crowd && typeof r.scores.crowd.crps === 'number');

function questionPage(id) {
  renderQuestion(id);
  return els['question-col'].innerHTML || '';
}
function forecastPage(id, entrant) {
  renderForecast(id, entrant);
  return els['forecast-col'].innerHTML || '';
}

if (scoredRanking) {
  const q = questionPage(scoredRanking.round_id);
  if (!/<th class="num">Loss<\/th>/.test(q) || /<th class="num">CRPS<\/th>/.test(q)) {
    problems.push(`${scoredRanking.round_id}: a scored ranking question shows the number template's columns`);
  }
  if (!q.includes('The released list')) problems.push(`${scoredRanking.round_id}: the released list is not shown`);
  if (!/class="qdue done">resolved/.test(q)) problems.push(`${scoredRanking.round_id}: a scored question is not shown as resolved`);
  if (q.includes('no number forecasts')) problems.push(`${scoredRanking.round_id}: says "no number forecasts" about a ranking`);
  const first = (scoredRanking.entries || [])[0];
  if (first) {
    const f = forecastPage(scoredRanking.round_id, first.entrant);
    if (!f.includes(first.loss.toFixed(3))) problems.push(`${scoredRanking.round_id}/${first.entrant}: the forecast page does not show its loss ${first.loss}`);
    if (!f.includes('The released list')) problems.push(`${scoredRanking.round_id}/${first.entrant}: the forecast page hides the released list`);
    if (/CRPS/.test(f)) problems.push(`${scoredRanking.round_id}/${first.entrant}: a ranking forecast page mentions CRPS`);
  }
  console.log(`ranking question : ${scoredRanking.round_id}, ${(scoredRanking.entries || []).length} scored`);
} else {
  console.log('ranking question : none scored in this payload');
}

if (scoredProfile) {
  const q = questionPage(scoredProfile.round_id);
  if (!/<th class="num">Energy<\/th>/.test(q) || /<th class="num">CRPS<\/th>/.test(q)) {
    problems.push(`${scoredProfile.round_id}: a scored profile question shows the number template's columns`);
  }
  if (!q.includes('The released profile')) problems.push(`${scoredProfile.round_id}: the released profile is not shown`);
  if (!/class="qdue done">resolved/.test(q)) problems.push(`${scoredProfile.round_id}: a scored question is not shown as resolved`);
  const first = (scoredProfile.entries || [])[0];
  if (first) {
    const f = forecastPage(scoredProfile.round_id, first.entrant);
    if (!f.includes(first.energy.toFixed(3))) problems.push(`${scoredProfile.round_id}/${first.entrant}: the forecast page does not show its energy ${first.energy}`);
    if (!f.includes('The released profile')) problems.push(`${scoredProfile.round_id}/${first.entrant}: the forecast page hides the released profile`);
  }
  console.log(`profile question : ${scoredProfile.round_id}, ${(scoredProfile.entries || []).length} scored`);
} else {
  console.log('profile question : none scored in this payload');
}

if (numberRound) {
  const want = numberRound.scores.crowd.crps.toFixed(2);
  const q = questionPage(numberRound.round_id);
  const f = forecastPage(numberRound.round_id, 'crowd');
  if (!/<th class="num">CRPS<\/th>/.test(q)) problems.push(`${numberRound.round_id}: a number question lost its CRPS column`);
  // The crowd forecast is a quantile mixture; both pages must show the
  // pipeline's score, never a normal refitted to the mean and sd.
  const crowdRow = (q.split('<tr class="link"').find(x => x.includes('data-e="crowd"')) || '');
  if (!crowdRow.includes('>' + want + '<')) problems.push(`${numberRound.round_id}: the question page shows the crowd at something other than CRPS ${want}`);
  if (!f.includes('CRPS ' + want)) problems.push(`${numberRound.round_id}/crowd: the forecast page shows something other than CRPS ${want}`);
  console.log(`number question  : ${numberRound.round_id}, crowd CRPS ${want} on both pages`);
} else {
  console.log('number question  : no resolved round with a scored crowd forecast');
}

if (problems.length) {
  console.error('\n' + problems.join('\n'));
  process.exit(1);
}
console.log('\nquestion and forecast pages render each shape with its own score');
