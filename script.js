const steps = [
  { title: 'What symptoms are you experiencing?', subtitle: 'Choose anything you have noticed in the past 7 days.', hint: 'Select all that apply', options: ['Fever or feeling hot', 'Persistent cough or breathing trouble', 'Feeling very tired or weak', 'Headache or body ache', 'Stomach pain, vomiting, or loose motions', 'None of these'] },
  { title: 'Tell us a little more', subtitle: 'These details help us understand your situation better.', hint: 'Select all that apply', options: ['Symptoms for more than 3 days', 'I am pregnant or recently gave birth', 'I have diabetes, BP, or heart condition', 'Child under 5 or adult over 60', 'Unable to eat or drink normally', 'None of these'] },
  { title: 'Do you have any readings?', subtitle: 'Optional — enter measurements from a local health worker or device.', hint: 'You can skip this step', inputs: true }
];
let step = 0, answers = [[], [], []];
const $ = id => document.getElementById(id);
function renderQuestion(){
  const data = steps[step]; $('stepText').textContent = `STEP ${step + 1} OF 3`;
  document.querySelectorAll('.progress span').forEach((el,i)=>{el.classList.toggle('active',i===step); el.textContent=i<step?'✓':i+1});
  $('backBtn').hidden = step === 0; $('hint').textContent=data.hint;
  $('questionContent').innerHTML = data.inputs ? `<div class="question"><h3>${data.title}</h3><p>${data.subtitle}</p><div class="options readings"><button type="button" class="option camera-option" id="openCamera"><span class="check">⌁</span><span><b>Check pulse with finger</b><br /><small>Rear camera + flash · estimate only</small></span><span>→</span></button><label class="option">Temperature <input type="number" id="temp" placeholder="e.g. 98.6" min="90" max="110" step=".1" /> °F</label><label class="option">Blood pressure <input type="text" id="bp" placeholder="e.g. 120/80" /></label><label class="option">Blood sugar <input type="number" id="sugar" placeholder="optional" /> mg/dL</label></div></div>` : `<div class="question"><h3>${data.title}</h3><p>${data.subtitle}</p><div class="options">${data.options.map(o=>`<button type="button" class="option ${answers[step].includes(o)?'selected':''}" data-value="${o}" onclick="selectOption(this.dataset.value)"><span class="check">${answers[step].includes(o)?'✓':''}</span>${o}</button>`).join('')}</div></div>`;
  $('nextBtn').textContent = step === 2 ? 'See my results →' : 'Continue →'; $('nextBtn').disabled = !data.inputs && answers[step].length===0;
  if (data.inputs) $('openCamera').onclick = openCamera;
}
window.selectOption = value => {
  if (value === 'None of these') answers[step] = [value];
  else {
    answers[step] = answers[step].filter(x => x !== 'None of these');
    answers[step] = answers[step].includes(value) ? answers[step].filter(x => x !== value) : [...answers[step], value];
  }
  renderQuestion();
};
async function showResults(){
  $('nextBtn').disabled = true;
  $('nextBtn').textContent = 'Analysing your health check…';
  try {
    const response = await fetch('/api/triage', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answers }) });
    if (!response.ok) throw new Error('Triage request failed');
    const { result } = await response.json();
    $('riskPill').textContent = `${result.priority} PRIORITY`;
    $('riskScore').innerHTML = `<b>${result.score}</b><small>risk score</small>`;
    $('riskTitle').textContent = result.title;
    $('riskAdvice').textContent = result.advice;
    $('resultHeading').textContent = result.priority === 'HIGH' ? 'You did the right thing by checking in.' : result.priority === 'MODERATE' ? 'Let’s get you the right care.' : 'A reassuring first check.';
    const signals = result.possible_risks?.length ? result.possible_risks.map(item => `${item.label} (${item.screening_score}%)`).join(' · ') : 'No condition-specific risk signals';
    $('resultText').textContent = `AI screening signals: ${signals}. Recommendation: ${result.referral_window}. This is screening support, not a diagnosis — clinician confirmation is required.`;
    $('screening').hidden=true;$('results').hidden=false;$('results').scrollIntoView({behavior:'smooth'});
  } catch (error) {
    $('nextBtn').disabled = false;
    $('nextBtn').textContent = 'Try again — backend unavailable';
    alert('Please start the Python backend with: python app.py');
  }
}
$('startCheck').onclick=()=>$('screening').scrollIntoView({behavior:'smooth'}); $('howItWorks').onclick=()=>$('screening').scrollIntoView({behavior:'smooth'});
$('nextBtn').onclick=()=>{if(step<2){step++;renderQuestion()}else showResults()}; $('backBtn').onclick=()=>{step--;renderQuestion()};
$('restart').onclick=()=>{step=0;answers=[[],[],[]];$('results').hidden=true;$('screening').hidden=false;renderQuestion();$('screening').scrollIntoView({behavior:'smooth'})};
$('teleButton').onclick=()=>$('teleModal').hidden=false;$('closeModal').onclick=()=>$('teleModal').hidden=true;$('confirmCall').onclick=()=>{$('teleModal').hidden=true;$('toast').classList.add('show');setTimeout(()=>$('toast').classList.remove('show'),3500)};
let cameraStream;
async function openCamera(){
  $('cameraModal').hidden = false;
  $('sensorResult').hidden = true;
  $('scanCamera').disabled = false;
  $('scanCamera').textContent = 'Start 20-second pulse check';
  $('cameraState').textContent = 'Requesting rear camera permission…';
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { exact: 'environment' }, width: { ideal: 640 }, height: { ideal: 480 } }, audio: false });
    $('cameraFeed').srcObject = cameraStream;
    const track = cameraStream.getVideoTracks()[0];
    await track.applyConstraints({ advanced: [{ torch: true }] }).catch(() => {});
    $('cameraState').textContent = 'Cover camera + flash with one fingertip';
  } catch (error) {
    $('cameraState').textContent = 'Camera unavailable — please allow permission';
    $('scanCamera').disabled = true;
  }
}
function closeCamera(){
  if (cameraStream) cameraStream.getTracks().forEach(track => track.stop());
  cameraStream = null;
  $('cameraFeed').srcObject = null;
  $('cameraModal').hidden = true;
}
$('closeCamera').onclick = closeCamera;
function estimatePulse(samples, durationSeconds) {
  const mean = samples.reduce((sum, value) => sum + value, 0) / samples.length;
  const smooth = samples.map((_, index) => samples.slice(Math.max(0, index - 2), index + 3).reduce((sum, value) => sum + value, 0) / Math.min(5, index + 3, samples.length - Math.max(0, index - 2)));
  const peaks = [];
  for (let index = 2; index < smooth.length - 2; index++) {
    if (smooth[index] > mean && smooth[index] > smooth[index - 1] && smooth[index] >= smooth[index + 1] && (!peaks.length || index - peaks.at(-1) > 3)) peaks.push(index);
  }
  const bpm = Math.round((peaks.length / durationSeconds) * 60);
  return bpm >= 40 && bpm <= 180 ? bpm : null;
}
$('scanCamera').onclick = () => {
  $('scanCamera').disabled = true;
  $('scanCamera').textContent = 'Measuring…';
  $('cameraState').textContent = 'Keep finger still — 20 seconds';
  const canvas = $('pulseCanvas'), context = canvas.getContext('2d', { willReadFrequently: true }), samples = [];
  const startedAt = Date.now();
  const timer = setInterval(() => {
    const video = $('cameraFeed');
    if (!video.videoWidth) return;
    canvas.width = 24; canvas.height = 24;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    let red = 0;
    for (let index = 0; index < pixels.length; index += 4) red += pixels[index];
    samples.push(red / (pixels.length / 4));
    const secondsLeft = Math.max(0, Math.ceil((20000 - (Date.now() - startedAt)) / 1000));
    $('cameraState').textContent = `Keep finger still — ${secondsLeft}s`;
    if (Date.now() - startedAt < 20000) return;
    clearInterval(timer);
    const averageRed = samples.reduce((sum, value) => sum + value, 0) / samples.length;
    const bpm = averageRed > 55 ? estimatePulse(samples, 20) : null;
    $('cameraState').textContent = bpm ? 'Pulse estimate complete' : 'Signal too weak — try again with flash covered';
    $('sensorResult').textContent = bpm ? `Estimated pulse: ${bpm} BPM. Prototype estimate only; do not use for diagnosis or urgent decisions.` : 'We could not get a reliable finger signal. Cover both rear camera and flash fully, hold still, and try again.';
    $('sensorResult').hidden = false;
    $('scanCamera').disabled = false;
    $('scanCamera').textContent = 'Measure again';
  }, 100);
};
renderQuestion();
