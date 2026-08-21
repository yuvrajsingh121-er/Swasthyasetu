"use client";

import { useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const SYMPTOMS = [
  "Fever or feeling hot", "Persistent cough or breathing trouble", "Feeling very tired or weak", "Headache or body ache",
  "Stomach pain, vomiting, or loose motions", "Chest pain or pressure", "Rash, body pain, or bleeding", "Dizziness or fainting",
  "Symptoms for more than 3 days", "I am pregnant or recently gave birth", "I have diabetes, BP, or heart condition", "Child under 5 or adult over 60", "Unable to eat or drink normally",
];
type Result = { priority:string; score:number; title:string; advice:string; referral_window:string; possible_risks:{label:string;score:number;evidence:string[]}[] };
type Profile = { name:string; age:string; gender:string; phone:string; abha:string; pregnancy:boolean; chronic:string; allergies:string; bloodGroup:string };
const emptyProfile:Profile = {name:"",age:"",gender:"",phone:"",abha:"",pregnancy:false,chronic:"",allergies:"",bloodGroup:""};

export default function Home() {
  const [tab, setTab] = useState<"screen"|"worker"|"admin">("screen"), [step,setStep]=useState(0), [profile,setProfile]=useState<Profile>(emptyProfile);
  const [symptoms,setSymptoms]=useState<string[]>([]),  [consent,setConsent]=useState(false), [result,setResult]=useState<Result|null>(null), [apiError,setApiError]=useState("");
  const [temperature,setTemperature]=useState(""),[bp,setBp]=useState(""),[sugar,setSugar]=useState(""),[spo2,setSpo2]=useState(""),[pulse,setPulse]=useState<number|null>(null);
  const [patientId, setPatientId] = useState<string | null>(null);
  const [cameraOpen,setCameraOpen]=useState(false),[scanStatus,setScanStatus]=useState(""),[language,setLanguage]=useState("English"),[toast,setToast]=useState("");
  const [location,setLocation]=useState<{lat:number;lng:number}|null>(null),[offline,setOffline]=useState(false),stream=useRef<MediaStream|null>(null),video=useRef<HTMLVideoElement>(null);
  const update=(key:keyof Profile,value:string|boolean)=>setProfile(p=>({...p,[key]:value}));
  const toggle=(value:string)=>setSymptoms(values=>values.includes(value)?values.filter(v=>v!==value):[...values,value]);
  const notify=(message:string)=>{setToast(message);window.setTimeout(()=>setToast(""),3600)};
  useEffect(()=>{const saved=localStorage.getItem("swasthya-draft");if(saved){try{const value=JSON.parse(saved);setProfile(value.profile??emptyProfile);setSymptoms(value.symptoms??[]);setTemperature(value.temperature??"");setBp(value.bp??"");setSugar(value.sugar??"");setSpo2(value.spo2??"");setOffline(true)}catch{}}},[]);
  useEffect(()=>{localStorage.setItem("swasthya-draft",JSON.stringify({profile,symptoms,temperature,bp,sugar,spo2}));},[profile,symptoms,temperature,bp,sugar,spo2]);
  function speak(text:string){ const Speech=window.speechSynthesis;if(!Speech){notify("Voice output is not supported in this browser.");return;} Speech.cancel();Speech.speak(new SpeechSynthesisUtterance(text)); }
  function getLocation(){navigator.geolocation?.getCurrentPosition(position=>{setLocation({lat:position.coords.latitude,lng:position.coords.longitude});notify("Location saved for nearest-care referral.");},()=>notify("Location permission was not granted. You can still use the suggested care centre."));}
  async function submit() {
  if (!consent) {
    setApiError("Please accept the consent statement before continuing.");
    return;
  }

  setApiError("");

  try {
    // 1️⃣ Create patient first
    let currentPatientId = patientId;

    if (!currentPatientId) {
      const patientPayload = {
        name: profile.name || null,
        age: profile.age ? Number(profile.age) : null,
        gender: profile.gender || null,
        phone: profile.phone || null,
        abha_id: profile.abha || null,
        pregnancy: profile.pregnancy,
        chronic: profile.chronic || null,
        allergies: profile.allergies || null,
        blood_group: profile.bloodGroup || null,
      };

      console.log("➡️ Creating patient:", patientPayload);

      const patientResponse = await fetch(
        `${API}/api/v1/patients`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(patientPayload),
        }
      );

      console.log("⬅️ Patient status:", patientResponse.status);

      if (!patientResponse.ok) {
        const errorText = await patientResponse.text();
        console.error("❌ Patient creation failed:", errorText);
        throw new Error("Patient creation failed");
      }

      const patientData = await patientResponse.json();

      console.log("👤 Patient response:", patientData);

      currentPatientId =
        patientData.patient_id ??
        patientData.id ??
        patientData.patient?.id;

      if (!currentPatientId) {
        throw new Error("Patient ID missing from backend response");
      }

      setPatientId(String(currentPatientId));
    }

    // 2️⃣ Send triage request
    const payload = {
      patient_id: currentPatientId,

      symptoms,

      temperature_f: temperature
        ? Number(temperature)
        : null,

      blood_pressure: bp || null,

      blood_sugar: sugar
        ? Number(sugar)
        : null,

      spo2: spo2
        ? Number(spo2)
        : null,

      pulse_estimate: pulse,

      abha_id: profile.abha || null,

      consent,
    };

    console.log("➡️ Sending triage:", payload);
    console.log(
      "🌐 API:",
      `${API}/api/v1/triage`
    );

    const response = await fetch(
      `${API}/api/v1/triage`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      }
    );

    console.log(
      "⬅️ Triage status:",
      response.status
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error(
        "❌ Triage error:",
        errorText
      );

      throw new Error(
        `Backend returned ${response.status}`
      );
    }

    const data = await response.json();

    console.log(
      "⬅️ Full triage response:",
      data
    );

    if (!data.result) {
      throw new Error(
        "Backend response does not contain result"
      );
    }

    // 3️⃣ Show result
    setResult(data.result);
    setStep(3);

    if (data.result.priority === "EMERGENCY") {
      notify(
        "🚨 Emergency warning sign detected. Seek immediate medical care."
      );
    } else if (data.result.priority === "HIGH") {
      notify(
        "High-priority referral created. Please seek care today."
      );
    }

  } catch (error) {
    console.error(
      "❌ TRIAGE REQUEST FAILED:",
      error
    );

    setApiError(
      "Backend request failed. Check the FastAPI server and API response."
    );
  }
}
  async function openCamera(){setCameraOpen(true);if(!navigator.mediaDevices?.getUserMedia){setScanStatus("Camera requires HTTPS or localhost.");return;}setScanStatus("Allow camera access, then cover rear camera and flash with one fingertip.");try{stream.current=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:"environment"},width:{ideal:640},height:{ideal:480}},audio:false});if(video.current)video.current.srcObject=stream.current;const track=stream.current.getVideoTracks()[0];await track.applyConstraints({advanced:[{torch:true}]} as unknown as MediaTrackConstraints).catch(()=>setScanStatus("Camera allowed. Flashlight is not supported; use bright light."));}catch(error){setScanStatus(`Camera permission not granted (${error instanceof DOMException?error.name:"error"}).`);}}
  function closeCamera(){stream.current?.getTracks().forEach(track=>track.stop());stream.current=null;setCameraOpen(false);}
  function measurePulse(){if(!video.current?.videoWidth){setScanStatus("Camera is still loading.");return;}setScanStatus("Measuring for 20 seconds — keep finger still.");const canvas=document.createElement("canvas"),ctx=canvas.getContext("2d",{willReadFrequently:true});if(!ctx)return;canvas.width=24;canvas.height=24;const samples:number[]=[],started=Date.now();const timer=window.setInterval(()=>{if(!video.current)return;ctx.drawImage(video.current,0,0,24,24);const pixels=ctx.getImageData(0,0,24,24).data;let red=0;for(let i=0;i<pixels.length;i+=4)red+=pixels[i];samples.push(red/(pixels.length/4));const left=Math.max(0,Math.ceil((20000-(Date.now()-started))/1000));setScanStatus(`Measuring — ${left}s remaining`);if(Date.now()-started<20000)return;window.clearInterval(timer);const mean=samples.reduce((a,b)=>a+b,0)/samples.length;const peaks=samples.filter((v,i)=>i>1&&i<samples.length-1&&v>mean&&v>samples[i-1]&&v>=samples[i+1]).length;const estimate=Math.round(peaks*3);if(mean>55&&estimate>=40&&estimate<=180){setPulse(estimate);setScanStatus(`Pulse estimate saved: ${estimate} BPM. Not medical-grade.`)}else setScanStatus("Signal weak. Cover flash and rear camera fully, then try again.");},100);}
  function exportRecord(){const record={profile,symptoms,vitals:{temperature,bp,sugar,spo2,pulse},result,location,consent:true,format:"ABDM-ready prototype JSON"};const blob=new Blob([JSON.stringify(record,null,2)],{type:"application/json"});const link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download="swasthya-referral.json";link.click();URL.revokeObjectURL(link.href);}
  async function exportPdf(){if(!result)return;try{const response=await fetch(`${API}/api/v1/report.pdf`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({profile,symptoms,vitals:{temperature,bp,sugar,spo2,pulse},result,nearest_centre:nearest})});if(!response.ok)throw new Error();const blob=await response.blob(),link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download="swasthya-medical-report.pdf";link.click();URL.revokeObjectURL(link.href);notify("Medical report PDF downloaded.");}catch{notify("PDF export failed. Confirm that the FastAPI backend is running.");}}
  const nearest="Rampur Community Health Centre";
  return <main className="mx-auto min-h-screen max-w-6xl bg-cream px-5 py-7 sm:px-12"><header className="flex flex-wrap items-center justify-between gap-4 border-b border-emerald-100 pb-5"><div><b className="text-2xl">✦ Swasthya<span className="text-forest">Setu</span></b><p className="mt-1 text-xs text-slate-500">AI-assisted rural healthcare access</p></div><div className="flex items-center gap-3"><select className="rounded-full border border-emerald-200 bg-white px-3 py-2 text-sm" value={language} onChange={e=>setLanguage(e.target.value)}><option>English</option><option>हिंदी</option><option>বাংলা</option><option>मराठी</option></select><button className="rounded-full border border-emerald-200 px-3 py-2 text-sm" onClick={()=>speak("Welcome to SwasthyaSetu. Start your health check.")}>🔊 Voice</button></div></header>
    <nav className="mt-5 flex gap-6 text-sm font-semibold"><button className={tab==="screen"?"text-forest":"text-slate-500"} onClick={()=>setTab("screen")}>Patient screening</button><button className={tab==="worker"?"text-forest":"text-slate-500"} onClick={()=>setTab("worker")}>ASHA worker dashboard</button><button className={tab==="admin"?"text-forest":"text-slate-500"} onClick={()=>setTab("admin")}>Admin insights</button></nav>
    {tab==="worker"?<WorkerDashboard result={result} offline={offline} onSync={()=>{setOffline(false);notify("Offline records synced securely.");}}/>:tab==="admin"?<AdminDashboard result={result}/>: !result?<section className="grid gap-10 py-10 md:grid-cols-[.8fr_1.2fr]"><aside><p className="text-xs font-bold tracking-widest text-forest">EARLY SCREENING · PRIVATE BY DESIGN</p><h1 className="font-display mt-4 text-5xl font-bold leading-tight">Care before<br/><i className="text-forest">it becomes urgent.</i></h1><p className="mt-5 max-w-sm text-slate-600">Multilingual health screening, optional camera pulse estimate, and a clear referral pathway for rural families.</p><div className="mt-8 space-y-3 text-sm text-slate-600"><p>✓ Offline draft saved on this device</p><p>✓ Explainable AI risk factors</p><p>✓ ASHA-friendly, mobile-first workflow</p><button className="text-forest underline" onClick={()=>{localStorage.removeItem("swasthya-draft");setProfile(emptyProfile);setSymptoms([]);notify("Local health draft deleted.");}}>Delete my local data</button></div></aside><section className="rounded-3xl bg-white p-6 shadow-lg"><div className="flex items-center justify-between"><span className="text-xs font-bold tracking-widest text-forest">STEP {step+1} OF 3</span><span className="text-xs text-slate-400">{offline?"Offline draft active":"Secure session"}</span></div>{step===0&&<ProfileStep profile={profile} update={update}/>} {step===1&&<SymptomsStep symptoms={symptoms} toggle={toggle}/>} {step===2&&<VitalsStep temperature={temperature} setTemperature={setTemperature} bp={bp} setBp={setBp} sugar={sugar} setSugar={setSugar} spo2={spo2} setSpo2={setSpo2} pulse={pulse} openCamera={openCamera}/>}<label className="mt-5 flex gap-2 text-xs text-slate-500"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/> I consent to secure screening data use and understand this is not a diagnosis.</label>{apiError&&<p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{apiError}</p>}<div className="mt-6 flex justify-between"><button className="text-sm text-slate-500" disabled={!step} onClick={()=>setStep(step-1)}>← Back</button><button className="primary" disabled={step===0&&!profile.age} onClick={()=>step<2?setStep(step+1):submit()}>{step===2?"Generate risk report →":"Continue →"}</button></div></section></section>:<ResultPage result={result} profile={profile} pulse={pulse} nearest={nearest} location={location} getLocation={getLocation} exportRecord={exportRecord} exportPdf={exportPdf} restart={()=>{setResult(null);setStep(0);}}/>}
    {cameraOpen&&<div className="fixed inset-0 z-20 grid place-items-center bg-black/50 p-5"><div className="w-full max-w-md rounded-3xl bg-cream p-6"><button className="float-right text-xl" onClick={closeCamera}>×</button><p className="text-xs font-bold tracking-widest text-forest">PULSE SENSOR PROTOTYPE</p><h2 className="font-display mt-2 text-3xl">Finger pulse check</h2><video ref={video} className="sensor-video mt-5" autoPlay muted playsInline/><p className="mt-3 text-sm text-slate-600">{scanStatus}</p><button className="primary mt-5 w-full" onClick={measurePulse}>Start 20-second pulse check</button></div></div>}{toast&&<div className="fixed bottom-6 left-1/2 z-30 -translate-x-1/2 rounded-full bg-ink px-5 py-3 text-sm text-white">{toast}</div>}</main>;
}

function ProfileStep({profile,update}:{profile:Profile;update:(key:keyof Profile,value:string|boolean)=>void}){return <div className="mt-5"><h2 className="font-display text-2xl">Patient profile</h2><p className="mt-1 text-sm text-slate-500">Fields marked optional help the referral team provide safer care.</p><div className="mt-4 grid gap-3 sm:grid-cols-2"><input className="option" placeholder="Patient name (optional)" value={profile.name} onChange={e=>update("name",e.target.value)}/><input className="option" placeholder="Age *" type="number" value={profile.age} onChange={e=>update("age",e.target.value)}/><select className="option" value={profile.gender} onChange={e=>update("gender",e.target.value)}><option value="">Gender (optional)</option><option>Female</option><option>Male</option><option>Other</option></select><input className="option" placeholder="Phone (optional)" value={profile.phone} onChange={e=>update("phone",e.target.value)}/><input className="option" placeholder="ABHA ID (optional)" value={profile.abha} onChange={e=>update("abha",e.target.value)}/><select className="option" value={profile.bloodGroup} onChange={e=>update("bloodGroup",e.target.value)}><option value="">Blood group (optional)</option>{["A+","A-","B+","B-","O+","O-","AB+","AB-"].map(x=><option key={x}>{x}</option>)}</select><input className="option sm:col-span-2" placeholder="Existing conditions / medicines (optional)" value={profile.chronic} onChange={e=>update("chronic",e.target.value)}/><input className="option sm:col-span-2" placeholder="Allergies (optional)" value={profile.allergies} onChange={e=>update("allergies",e.target.value)}/></div><label className="mt-4 flex gap-2 text-sm"><input type="checkbox" checked={profile.pregnancy} onChange={e=>update("pregnancy",e.target.checked)}/> Pregnant or recently gave birth</label></div>}
function SymptomsStep({symptoms,toggle}:{symptoms:string[];toggle:(x:string)=>void}){return <div className="mt-5"><h2 className="font-display text-2xl">Symptoms & warning signs</h2><p className="mt-1 text-sm text-slate-500">Select everything noticed in the last 7 days.</p><div className="mt-4 grid gap-2 sm:grid-cols-2">{SYMPTOMS.map(x=><button className={`option text-sm ${symptoms.includes(x)?"selected":""}`} onClick={()=>toggle(x)} key={x}>{symptoms.includes(x)?"✓ ":"○ "}{x}</button>)}</div></div>}
function VitalsStep({temperature,setTemperature,bp,setBp,sugar,setSugar,spo2,setSpo2,pulse,openCamera}:{temperature:string;setTemperature:(x:string)=>void;bp:string;setBp:(x:string)=>void;sugar:string;setSugar:(x:string)=>void;spo2:string;setSpo2:(x:string)=>void;pulse:number|null;openCamera:()=>void}){return <div className="mt-5"><h2 className="font-display text-2xl">Vitals & optional sensor</h2><p className="mt-1 text-sm text-slate-500">Use readings from a local health worker/device if available.</p><div className="mt-4 grid gap-3 sm:grid-cols-2"><input className="option" placeholder="Temperature °F" type="number" value={temperature} onChange={e=>setTemperature(e.target.value)}/><input className="option" placeholder="BP e.g. 120/80" value={bp} onChange={e=>setBp(e.target.value)}/><input className="option" placeholder="Blood sugar mg/dL" type="number" value={sugar} onChange={e=>setSugar(e.target.value)}/><input className="option" placeholder="SpO₂ %" type="number" value={spo2} onChange={e=>setSpo2(e.target.value)}/></div><button className="option mt-4" onClick={openCamera}>⌁ <b>Check pulse with finger</b><br/><small>Rear camera + flash · estimate only · not medical-grade</small></button>{pulse&&<p className="mt-3 rounded-lg bg-green-50 p-3 text-sm text-forest">Pulse estimate saved: {pulse} BPM</p>}</div>}
function ResultPage({result,profile,pulse,nearest,location,getLocation,exportRecord,exportPdf,restart}:{result:Result;profile:Profile;pulse:number|null;nearest:string;location:{lat:number;lng:number}|null;getLocation:()=>void;exportRecord:()=>void;exportPdf:()=>void;restart:()=>void}){const route=location?`https://www.google.com/maps/dir/${location.lat},${location.lng}/${encodeURIComponent(nearest)}`:`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(nearest)}`;return <section className="py-10"><p className="text-xs font-bold tracking-widest text-forest">EXPLAINABLE AI SCREENING REPORT</p><h1 className="font-display mt-3 text-4xl">{result.title}</h1><p className="mt-3 text-slate-600">Screening support only—not a diagnosis. A clinician must confirm any condition.</p><div className="mt-7 grid gap-5 lg:grid-cols-3"><article className="rounded-2xl bg-ink p-7 text-white"><span className="rounded-full bg-forest px-3 py-1 text-xs">{result.priority} PRIORITY</span><p className="mt-6 text-6xl font-bold">{result.score}</p><p className="mt-2 text-slate-300">risk score</p><p className="mt-5 text-sm leading-6">{result.advice}</p>{pulse&&<p className="mt-5 border-t border-white/20 pt-4 text-sm">Camera pulse estimate: {pulse} BPM</p>}</article><article className="rounded-2xl bg-white p-7"><h2 className="font-display text-2xl">Why this result?</h2>{result.possible_risks.length?result.possible_risks.map(signal=><div className="mt-3 rounded-lg bg-green-50 p-3 text-sm" key={signal.label}><b>{signal.label} · {signal.score}%</b><p className="mt-1 text-slate-600">Based on: {signal.evidence.join(", ")}</p></div>):<p className="mt-4 text-sm text-slate-600">No condition-specific risk signals were found.</p>}</article><article className="rounded-2xl border border-emerald-200 bg-emerald-50 p-7"><p className="text-xs font-bold tracking-widest text-forest">REFERRAL SLIP</p><h2 className="font-display mt-3 text-2xl">{nearest}</h2><p className="mt-2 text-sm text-slate-600">Suggested next step: {result.referral_window}<br/>Open today · Teleconsultation available</p><div className="mt-6 flex flex-wrap gap-2"><button className="primary" onClick={getLocation}>⌖ Use my location</button><a className="rounded-full border border-emerald-300 px-4 py-3 text-sm font-bold text-forest" href={route} target="_blank">Route →</a><button className="rounded-full border border-emerald-300 px-4 py-3 text-sm font-bold text-forest" onClick={exportPdf}>Download medical PDF</button><button className="rounded-full border border-emerald-300 px-4 py-3 text-sm font-bold text-forest" onClick={exportRecord}>Export JSON</button></div><p className="mt-5 text-xs text-slate-500">Medical PDF and ABDM-ready JSON · ABHA: {profile.abha||"not provided"}</p></article></div><Telemedicine/><div className="mt-8 flex flex-wrap gap-4"><button className="primary" onClick={()=>window.print()}>Print referral slip</button><button className="text-sm font-bold text-forest" onClick={restart}>← Start another check</button></div></section>}
function WorkerDashboard({result,offline,onSync}:{result:Result|null;offline:boolean;onSync:()=>void}){return <section className="py-10"><p className="text-xs font-bold tracking-widest text-forest">ASHA WORKER VIEW</p><h1 className="font-display mt-3 text-4xl">Village health follow-up, in one place.</h1><div className="mt-8 grid gap-4 md:grid-cols-3"><article className="rounded-2xl bg-white p-6"><p className="text-sm text-slate-500">Current screening</p><p className="mt-2 text-4xl font-bold">{result?1:0}</p><p className="mt-2 text-sm">Current priority: {result?.priority??"No assessment"}</p></article><article className="rounded-2xl bg-white p-6"><p className="text-sm text-slate-500">Offline data</p><p className="mt-2 text-4xl font-bold">{offline?1:0}</p><p className="mt-2 text-sm">Encrypted draft on this device</p><button className="mt-4 text-sm font-bold text-forest" onClick={onSync}>Sync now →</button></article><article className="rounded-2xl bg-white p-6"><p className="text-sm text-slate-500">Follow-up action</p><p className="mt-2 text-xl font-bold">{result?.priority==="HIGH"?"Refer today":"Schedule review"}</p><p className="mt-2 text-sm">Patient data shown only with consent.</p></article></div><div className="mt-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-6"><h2 className="font-display text-2xl">Integration-ready</h2><p className="mt-2 max-w-2xl text-sm text-slate-600">ABHA ID capture, structured referral export, and consent status are included. Connect official ABDM/Ayushman Bharat services only with approved credentials and data-sharing agreements.</p></div></section>}
function Telemedicine() {
  const [booked, setBooked] = useState(false);
  const [message, setMessage] = useState("");
  const [file, setFile] = useState("");
  const [reminder, setReminder] = useState(false);

  function createReminder() {
    if (
      "Notification" in window &&
      Notification.permission === "default"
    ) {
      Notification.requestPermission();
    }

    setReminder(true);

    window.setTimeout(() => {
      if (
        "Notification" in window &&
        Notification.permission === "granted"
      ) {
        new Notification("SwasthyaSetu follow-up", {
          body: "Time to take medicine or complete your health follow-up.",
        });
      }
    }, 60000);
  }

  return (
    <section className="mt-6 grid gap-5 lg:grid-cols-2">

      {/* TELECONSULTATION */}
      <article className="rounded-2xl bg-white p-6">
        <p className="text-xs font-bold tracking-widest text-forest">
          TELECONSULTATION
        </p>

        <h2 className="font-display mt-2 text-2xl">
          Talk to Dr. Meera
        </h2>

        <p className="mt-2 text-sm text-slate-600">
          Hindi & English · Estimated wait: 5 minutes · Screening summary
          shared only after consent.
        </p>

        <div className="mt-4 flex gap-2">
          <button
            className="primary"
            onClick={() => setBooked(true)}
          >
            {booked
              ? "Consultation requested ✓"
              : "Request secure call"}
          </button>

          <input
            className="max-w-[180px] text-sm"
            type="file"
            accept="image/*,.pdf"
            onChange={(e) =>
              setFile(e.target.files?.[0]?.name ?? "")
            }
          />
        </div>

        {file && (
          <p className="mt-2 text-xs text-slate-500">
            Prescription/report selected: {file}
          </p>
        )}

        {booked && (
          <div className="mt-4 rounded-lg bg-green-50 p-3">
            <input
              className="w-full bg-transparent text-sm outline-none"
              placeholder="Message doctor (prototype chat)"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
            />

            {message && (
              <p className="mt-2 text-xs text-forest">
                Message queued for consultation.
              </p>
            )}
          </div>
        )}
      </article>

      {/* REMINDERS */}
      <article className="rounded-2xl bg-white p-6">
        <p className="text-xs font-bold tracking-widest text-forest">
          REMINDERS
        </p>

        <h2 className="font-display mt-2 text-2xl">
          Stay on track
        </h2>

        <p className="mt-2 text-sm text-slate-600">
          Create a local medicine or follow-up reminder. It stays on this
          device.
        </p>

        <button
          className="primary mt-4"
          onClick={createReminder}
        >
          {reminder
            ? "Reminder set ✓"
            : "Set 1-minute demo reminder"}
        </button>

        <p className="mt-3 text-xs text-slate-500">
          In production, schedule reminders through approved SMS/WhatsApp
          providers with explicit consent.
        </p>
      </article>

    </section>
  );
}
function AdminDashboard({result}:{result:Result|null}){const current=result?.priority??"No data";return <section className="py-10"><p className="text-xs font-bold tracking-widest text-forest">PROGRAM INSIGHTS</p><h1 className="font-display mt-3 text-4xl">Privacy-safe screening trends.</h1><p className="mt-3 max-w-2xl text-slate-600">Demo dashboard uses only the current device session. Real village trends require consent, de-identification, and authorized data governance.</p><div className="mt-8 grid gap-4 md:grid-cols-3"><article className="rounded-2xl bg-white p-6"><p className="text-sm text-slate-500">Session screenings</p><p className="mt-2 text-4xl font-bold">{result?1:0}</p></article><article className="rounded-2xl bg-white p-6"><p className="text-sm text-slate-500">Current risk priority</p><p className="mt-2 text-3xl font-bold text-forest">{current}</p></article><article className="rounded-2xl bg-white p-6"><p className="text-sm text-slate-500">Referral conversion</p><p className="mt-2 text-3xl font-bold">—</p><p className="mt-1 text-xs text-slate-500">Connect hospital feedback API</p></article></div><div className="mt-6 rounded-2xl bg-ink p-7 text-white"><h2 className="font-display text-2xl">Disease-trend heatmap</h2><div className="mt-5 grid grid-cols-7 gap-2">{Array.from({length:28}).map((_,i)=><div className={`h-9 rounded ${i%9===0?"bg-red-400":i%4===0?"bg-amber-300":"bg-emerald-700"}`} key={i}/>)}</div><p className="mt-4 text-xs text-slate-300">Illustrative visual only — not population data.</p></div></section>}
