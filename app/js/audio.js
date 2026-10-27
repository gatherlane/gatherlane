// SPDX-License-Identifier: Apache-2.0
// Procedural lo-fi and office ambience with WebAudio. Silent until the user turns it on.
(function (G) {
  let ctx = null, master, musicBus, ambBus, timers = [], playing = { music: false, amb: false };

  function ensure() {
    if (ctx) return;
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    master = ctx.createGain(); master.gain.value = .5; master.connect(ctx.destination);
    musicBus = ctx.createGain(); musicBus.gain.value = 0; musicBus.connect(master);
    ambBus = ctx.createGain(); ambBus.gain.value = 0; ambBus.connect(master);
  }
  const mtof = m => 440 * Math.pow(2, (m - 69) / 12);

  function note(freq, t, dur, vol, type = 'triangle', dest = musicBus, cutoff = 1400) {
    const o = ctx.createOscillator(), g = ctx.createGain(), f = ctx.createBiquadFilter();
    o.type = type; o.frequency.value = freq; f.type = 'lowpass'; f.frequency.value = cutoff;
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(vol, t + .04); g.gain.exponentialRampToValueAtTime(.0005, t + dur);
    o.connect(f); f.connect(g); g.connect(dest); o.start(t); o.stop(t + dur + .05);
  }
  function noiseBuf(sec, brown) {
    const b = ctx.createBuffer(1, ctx.sampleRate * sec, ctx.sampleRate), d = b.getChannelData(0); let last = 0;
    for (let i = 0; i < d.length; i++) { const w = Math.random() * 2 - 1; if (brown) { last = (last + .02 * w) / 1.02; d[i] = last * 3.5; } else d[i] = w; }
    return b;
  }
  function hit(t, dur, vol, cutoff, type = 'highpass') {
    const s = ctx.createBufferSource(); s.buffer = noiseBuf(dur, false);
    const f = ctx.createBiquadFilter(); f.type = type; f.frequency.value = cutoff;
    const g = ctx.createGain(); g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(.0005, t + dur);
    s.connect(f); f.connect(g); g.connect(musicBus); s.start(t);
  }
  function kick(t) { const o = ctx.createOscillator(), g = ctx.createGain(); o.frequency.setValueAtTime(110, t); o.frequency.exponentialRampToValueAtTime(42, t + .18); g.gain.setValueAtTime(.5, t); g.gain.exponentialRampToValueAtTime(.001, t + .3); o.connect(g); g.connect(musicBus); o.start(t); o.stop(t + .32); }

  // Fmaj7 - Em7 - Dm7 - Cmaj7 with a slendro-ish lead on top
  const CHORDS = [[53, 57, 60, 64], [52, 55, 59, 62], [50, 53, 57, 60], [48, 52, 55, 59]];
  const LEAD = [72, 74, 76, 79, 81];
  let bar = 0, nextT = 0;
  const BPM = 72, BEAT = 60 / BPM;
  function schedule() {
    if (!playing.music) return;
    while (nextT < ctx.currentTime + 1.5) {
      const ch = CHORDS[bar % 4];
      ch.forEach((m, i) => note(mtof(m), nextT + i * .03, BEAT * 3.6, .05, 'triangle'));
      note(mtof(ch[0] - 12), nextT, BEAT * 1.8, .09, 'sine', musicBus, 500);
      note(mtof(ch[0] - 12), nextT + BEAT * 2, BEAT * 1.8, .08, 'sine', musicBus, 500);
      for (let b = 0; b < 4; b++) {
        if (b === 0 || b === 2) kick(nextT + b * BEAT);
        hit(nextT + b * BEAT + BEAT / 2, .05, .025, 6000);
        if (b === 1 || b === 3) hit(nextT + b * BEAT, .12, .04, 1800, 'bandpass');
      }
      if (bar % 2 === 1) for (let k = 0; k < 3; k++) if (Math.random() < .7) note(mtof(LEAD[Math.floor(Math.random() * LEAD.length)]), nextT + (k + 1) * BEAT * (.9 + Math.random() * .2), BEAT * 1.4, .035, 'sine', musicBus, 2600);
      nextT += BEAT * 4; bar++;
    }
  }
  let crackle;
  function startMusic() {
    ensure(); ctx.resume(); playing.music = true;
    musicBus.gain.cancelScheduledValues(ctx.currentTime); musicBus.gain.linearRampToValueAtTime(.9, ctx.currentTime + 1.5);
    nextT = ctx.currentTime + .1; schedule(); timers.push(setInterval(schedule, 400));
    crackle = ctx.createBufferSource(); const b = ctx.createBuffer(1, ctx.sampleRate * 3, ctx.sampleRate), d = b.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() < .0008 ? (Math.random() - .5) * .6 : (Math.random() - .5) * .006;
    crackle.buffer = b; crackle.loop = true; crackle.connect(musicBus); crackle.start();
  }
  function stopMusic() {
    if (!ctx) return; playing.music = false; timers.forEach(clearInterval); timers = [];
    musicBus.gain.linearRampToValueAtTime(0, ctx.currentTime + .6); if (crackle) { try { crackle.stop(ctx.currentTime + .7); } catch (e) {} crackle = null; }
  }
  let ambSrc, ambTimer;
  function startAmb() {
    ensure(); ctx.resume(); playing.amb = true;
    ambSrc = ctx.createBufferSource(); ambSrc.buffer = noiseBuf(4, true); ambSrc.loop = true;
    const f = ctx.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 380; const g = ctx.createGain(); g.gain.value = .35;
    ambSrc.connect(f); f.connect(g); g.connect(ambBus); ambSrc.start();
    ambBus.gain.linearRampToValueAtTime(.8, ctx.currentTime + 1.5);
    ambTimer = setInterval(() => {
      const t = ctx.currentTime + Math.random();
      if (Math.random() < .5) for (let i = 0; i < 4 + Math.random() * 8; i++) { const s = ctx.createBufferSource(); s.buffer = noiseBuf(.03, false); const ff = ctx.createBiquadFilter(); ff.type = 'bandpass'; ff.frequency.value = 2500 + Math.random() * 1500; const gg = ctx.createGain(); gg.gain.value = .05; s.connect(ff); ff.connect(gg); gg.connect(ambBus); s.start(t + i * (.08 + Math.random() * .1)); }
      if (Math.random() < .08) { const base = mtof([67, 69, 72, 74, 76][Math.floor(Math.random() * 5)]); [1, 2.76, 5.4].forEach((m, i) => note(base * m, t, 2.5 / (i + 1), .03 / (i + 1), 'sine', ambBus, 5000)); }
    }, 2500);
  }
  function stopAmb() { if (!ctx) return; playing.amb = false; clearInterval(ambTimer); ambBus.gain.linearRampToValueAtTime(0, ctx.currentTime + .6); if (ambSrc) { try { ambSrc.stop(ctx.currentTime + .7); } catch (e) {} ambSrc = null; } }

  G.GLAudio = {
    setMusic(on) { on ? (!playing.music && startMusic()) : stopMusic(); },
    setAmbience(on) { on ? (!playing.amb && startAmb()) : stopAmb(); },
    setVolume(v) { ensure(); master.gain.value = v; },
    state: () => ({ ...playing }),
  };
})(window);
