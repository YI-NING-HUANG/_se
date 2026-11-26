(() => {
  "use strict";

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d", { alpha: false });
  const W = canvas.width;
  const H = canvas.height;
  const GROUND_Y = 330;
  const DINO_X = 110;
  const BASE_SPEED = 360;
  const MAX_SPEED = 820;
  const GRAVITY = 2800;
  const JUMP_VELOCITY = -1010;
  const STORAGE = {
    high: "dinoRun.highScore",
    name: "dinoRun.playerName",
    muted: "dinoRun.muted",
  };
  const MONO = '"Cascadia Code", "SFMono-Regular", Consolas, monospace';

  const overlay = document.getElementById("overlay");
  const overlayEyebrow = document.getElementById("overlayEyebrow");
  const overlayTitle = document.getElementById("overlayTitle");
  const overlayText = document.getElementById("overlayText");
  const nameRow = document.getElementById("nameRow");
  const nameInput = document.getElementById("nameInput");
  const saveBtn = document.getElementById("saveBtn");
  const saveMsg = document.getElementById("saveMsg");
  const startBtn = document.getElementById("startBtn");
  const pauseBtn = document.getElementById("pauseBtn");
  const restartBtn = document.getElementById("restartBtn");
  const soundBtn = document.getElementById("soundBtn");
  const jumpBtn = document.getElementById("jumpBtn");
  const duckBtn = document.getElementById("duckBtn");
  const scoreDisplay = document.getElementById("scoreDisplay");
  const bestDisplay = document.getElementById("bestDisplay");
  const netBadge = document.getElementById("netBadge");
  const lbStatus = document.getElementById("lbStatus");
  const lbList = document.getElementById("lbList");
  const lbStats = document.getElementById("lbStats");
  const refreshBtn = document.getElementById("refreshBtn");
  const toast = document.getElementById("toast");

  function readStorage(key, fallback) {
    try {
      const value = localStorage.getItem(key);
      return value === null ? fallback : value;
    } catch (error) {
      return fallback;
    }
  }

  function writeStorage(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (error) {
      return;
    }
  }

  let state = "ready";
  let distance = 0;
  let speed = BASE_SPEED;
  let score = 0;
  let highScore = Number(readStorage(STORAGE.high, "0")) || 0;
  let muted = readStorage(STORAGE.muted, "0") === "1";
  let lastScoreUi = -1;
  let lastFrame = 0;
  let runTime = 0;
  let spawnGap = 520;
  let nightAlpha = 0;
  let duckHeld = false;
  let saveUsed = false;
  let toastTimer = 0;
  let audioContext = null;

  const dino = {
    x: DINO_X,
    y: GROUND_Y,
    vy: 0,
    onGround: true,
    ducking: false,
  };

  let obstacles = [];
  let clouds = [];
  let groundMarks = [];
  let particles = [];
  let stars = [];

  const DAY = {
    bg: [247, 247, 242],
    fg: [76, 76, 72],
    muted: [185, 185, 176],
    accent: [240, 90, 40],
  };
  const NIGHT = {
    bg: [16, 20, 27],
    fg: [230, 230, 223],
    muted: [75, 82, 96],
    accent: [255, 123, 79],
  };

  function mixColor(a, b, t) {
    const r = Math.round(a[0] + (b[0] - a[0]) * t);
    const g = Math.round(a[1] + (b[1] - a[1]) * t);
    const bl = Math.round(a[2] + (b[2] - a[2]) * t);
    return `rgb(${r}, ${g}, ${bl})`;
  }

  function palette() {
    return {
      bg: mixColor(DAY.bg, NIGHT.bg, nightAlpha),
      fg: mixColor(DAY.fg, NIGHT.fg, nightAlpha),
      muted: mixColor(DAY.muted, NIGHT.muted, nightAlpha),
      accent: mixColor(DAY.accent, NIGHT.accent, nightAlpha),
    };
  }

  function randomBetween(min, max) {
    return min + Math.random() * (max - min);
  }

  function initClouds() {
    clouds = [];
    for (let i = 0; i < 5; i += 1) {
      clouds.push({
        x: randomBetween(0, W),
        y: randomBetween(46, 150),
        scale: randomBetween(0.65, 1.25),
        speed: randomBetween(0.1, 0.24),
      });
    }
  }

  function makeGroundMark() {
    return {
      x: randomBetween(0, W),
      y: GROUND_Y + randomBetween(9, 28),
      w: randomBetween(5, 30),
      h: Math.random() < 0.72 ? 2 : 3,
    };
  }

  function initGroundMarks() {
    groundMarks = [];
    for (let i = 0; i < 48; i += 1) {
      groundMarks.push(makeGroundMark());
    }
  }

  function initStars() {
    stars = [];
    for (let i = 0; i < 64; i += 1) {
      stars.push({
        x: randomBetween(10, W - 10),
        y: randomBetween(24, 220),
        size: Math.random() < 0.8 ? 2 : 3,
        phase: randomBetween(0, Math.PI * 2),
      });
    }
  }

  function resetGame() {
    distance = 0;
    speed = BASE_SPEED;
    score = 0;
    runTime = 0;
    spawnGap = 520;
    nightAlpha = 0;
    duckHeld = false;
    saveUsed = false;
    obstacles = [];
    particles = [];
    dino.y = GROUND_Y;
    dino.vy = 0;
    dino.onGround = true;
    dino.ducking = false;
    initClouds();
    initGroundMarks();
    updateScoreUi();
  }

  function updateScoreUi() {
    if (score !== lastScoreUi) {
      lastScoreUi = score;
      scoreDisplay.textContent = String(score);
    }
    bestDisplay.textContent = String(highScore);
  }

  function showOverlay(mode, isRecord = false) {
    overlay.classList.remove("hidden");
    if (mode === "ready") {
      overlayEyebrow.textContent = "READY?";
      overlayTitle.textContent = "按空白鍵開始";
      overlayText.textContent = "跳過仙人掌、躲開翼龍，看看你能跑多遠。";
      nameRow.classList.add("hidden");
      startBtn.textContent = "開始遊戲";
    } else if (mode === "paused") {
      overlayEyebrow.textContent = "PAUSED";
      overlayTitle.textContent = "遊戲暫停";
      overlayText.textContent = "按 P 或點下方按鈕繼續。";
      nameRow.classList.add("hidden");
      startBtn.textContent = "繼續遊戲";
    } else if (mode === "over") {
      overlayEyebrow.textContent = "GAME OVER";
      overlayTitle.textContent = `本局 ${score} 分`;
      overlayText.textContent = isRecord
        ? "新紀錄！留下名字，讓大家知道你跑得多遠。"
        : `最高紀錄 ${highScore} 分。再試一次，超越自己。`;
      startBtn.textContent = "再玩一次";
      if (score > 0) {
        nameRow.classList.remove("hidden");
        nameInput.value = readStorage(STORAGE.name, "");
        saveBtn.disabled = false;
        saveBtn.textContent = "送出分數";
        saveMsg.textContent = isRecord ? "這是你的新高分。" : "";
      } else {
        nameRow.classList.add("hidden");
      }
    }
    updatePauseButton();
  }

  function hideOverlay() {
    overlay.classList.add("hidden");
  }

  function updatePauseButton() {
    pauseBtn.textContent = state === "paused" ? "繼續" : "暫停";
    pauseBtn.disabled = state !== "running" && state !== "paused";
  }

  function updateSoundButton() {
    soundBtn.textContent = muted ? "音效：關" : "音效：開";
    soundBtn.setAttribute("aria-pressed", String(!muted));
  }

  function setOnline(online) {
    netBadge.classList.remove("badge-wait", "badge-online", "badge-offline");
    netBadge.classList.add(online ? "badge-online" : "badge-offline");
    netBadge.textContent = online ? "排行榜連線" : "離線模式";
  }

  function showToast(message, duration = 2400) {
    toast.textContent = message;
    toast.classList.add("show");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => {
      toast.classList.remove("show");
    }, duration);
  }

  function beep(frequency, duration, type = "square", volume = 0.025) {
    if (muted) {
      return;
    }
    try {
      if (!audioContext) {
        const AudioCtor = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtor) {
          return;
        }
        audioContext = new AudioCtor();
      }
      if (audioContext.state === "suspended") {
        audioContext.resume();
      }
      const oscillator = audioContext.createOscillator();
      const gain = audioContext.createGain();
      oscillator.type = type;
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(volume, audioContext.currentTime);
      gain.gain.exponentialRampToValueAtTime(
        0.0001,
        audioContext.currentTime + duration
      );
      oscillator.connect(gain);
      gain.connect(audioContext.destination);
      oscillator.start();
      oscillator.stop(audioContext.currentTime + duration);
    } catch (error) {
      return;
    }
  }

  function startGame() {
    resetGame();
    state = "running";
    hideOverlay();
    lastFrame = performance.now();
    updatePauseButton();
    beep(460, 0.06, "square", 0.02);
  }

  function pauseGame() {
    if (state !== "running") {
      return;
    }
    state = "paused";
    duckHeld = false;
    dino.ducking = false;
    showOverlay("paused");
    beep(320, 0.05, "square", 0.015);
  }

  function resumeGame() {
    if (state !== "paused") {
      return;
    }
    state = "running";
    hideOverlay();
    lastFrame = performance.now();
    updatePauseButton();
  }

  function togglePause() {
    if (state === "running") {
      pauseGame();
    } else if (state === "paused") {
      resumeGame();
    }
  }

  function jumpOrStart() {
    if (state === "ready" || state === "over") {
      startGame();
      return;
    }
    if (state === "paused") {
      resumeGame();
      return;
    }
    if (!dino.onGround) {
      return;
    }
    dino.vy = JUMP_VELOCITY;
    dino.onGround = false;
    dino.ducking = false;
    spawnParticles(dino.x + 18, GROUND_Y, 5, palette().muted, 0.55);
    beep(540, 0.055, "square", 0.022);
  }

  function setDuck(active) {
    duckHeld = active;
    if (state !== "running") {
      dino.ducking = false;
      return;
    }
    if (active && !dino.onGround) {
      dino.vy += 260;
    }
    dino.ducking = active && dino.onGround;
  }

  function spawnParticles(x, y, count, color, strength = 1) {
    for (let i = 0; i < count; i += 1) {
      particles.push({
        x,
        y,
        vx: randomBetween(-180, 180) * strength,
        vy: randomBetween(-230, -30) * strength,
        size: randomBetween(2, 5),
        age: 0,
        life: randomBetween(0.32, 0.7),
        color,
      });
    }
  }

  function endGame() {
    state = "over";
    dino.ducking = false;
    duckHeld = false;
    const isRecord = score > highScore;
    if (isRecord) {
      highScore = score;
      writeStorage(STORAGE.high, String(highScore));
    }
    updateScoreUi();
    spawnParticles(dino.x + 24, dino.y - 22, 16, palette().accent, 1.3);
    beep(150, 0.18, "sawtooth", 0.05);
    window.setTimeout(() => beep(90, 0.24, "sawtooth", 0.04), 110);
    showOverlay("over", isRecord);
  }

  function dinoBox() {
    if (dino.ducking && dino.onGround) {
      return { x: dino.x + 2, y: dino.y - 26, w: 62, h: 24 };
    }
    return { x: dino.x + 8, y: dino.y - 46, w: 32, h: 42 };
  }

  function obstacleBox(obstacle) {
    if (obstacle.type === "bird") {
      return {
        x: obstacle.x + 8,
        y: obstacle.y + 8,
        w: obstacle.w - 16,
        h: obstacle.h - 14,
      };
    }
    return {
      x: obstacle.x + 4,
      y: obstacle.y + 4,
      w: obstacle.w - 8,
      h: obstacle.h - 6,
    };
  }

  function hitTest(a, b) {
    return (
      a.x < b.x + b.w &&
      a.x + a.w > b.x &&
      a.y < b.y + b.h &&
      a.y + a.h > b.y
    );
  }

  function spawnCactus(size) {
    const small = size === "small";
    const count = small
      ? 1 + Math.floor(Math.random() * 3)
      : 1 + Math.floor(Math.random() * 2);
    const unit = small ? 24 : 34;
    const step = small ? 27 : 38;
    const height = small ? 48 : 64;
    const variant = Math.floor(Math.random() * 3);
    for (let i = 0; i < count; i += 1) {
      obstacles.push({
        type: "cactus",
        size,
        x: W + 50 + i * step,
        y: GROUND_Y - height + (small ? 0 : Math.floor(Math.random() * 5)),
        w: unit,
        h: height,
        variant,
      });
    }
  }

  function spawnBird() {
    const heights = [GROUND_Y - 138, GROUND_Y - 98, GROUND_Y - 58];
    const y = heights[Math.floor(Math.random() * heights.length)];
    obstacles.push({
      type: "bird",
      x: W + 70,
      y,
      w: 54,
      h: 36,
      variant: Math.floor(Math.random() * 2),
    });
  }

  function spawnObstacle() {
    const roll = Math.random();
    if (score > 240 && roll < 0.26) {
      spawnBird();
    } else if (roll < 0.6) {
      spawnCactus("small");
    } else {
      spawnCactus("large");
    }
  }

  function update(dt) {
    runTime += dt;
    distance += speed * dt;
    speed = Math.min(MAX_SPEED, BASE_SPEED + distance * 0.012);
    score = Math.floor(distance / 10);

    if (!dino.onGround) {
      dino.vy += GRAVITY * dt;
      if (duckHeld) {
        dino.vy += GRAVITY * 0.55 * dt;
      }
      dino.y += dino.vy * dt;
      if (dino.y >= GROUND_Y) {
        dino.y = GROUND_Y;
        dino.vy = 0;
        dino.onGround = true;
        dino.ducking = duckHeld;
        spawnParticles(dino.x + 20, GROUND_Y, 4, palette().muted, 0.5);
      }
    }

    spawnGap -= speed * dt;
    if (spawnGap <= 0) {
      spawnObstacle();
      spawnGap = speed * randomBetween(1.0, 1.9) + 90;
    }

    const dBox = dinoBox();
    for (const obstacle of obstacles) {
      obstacle.x -= speed * dt;
      if (hitTest(dBox, obstacleBox(obstacle))) {
        endGame();
        return;
      }
    }
    obstacles = obstacles.filter((obstacle) => obstacle.x + obstacle.w > -60);

    for (const cloud of clouds) {
      cloud.x -= speed * cloud.speed * dt;
      if (cloud.x < -140) {
        cloud.x = W + randomBetween(40, 260);
        cloud.y = randomBetween(46, 150);
        cloud.scale = randomBetween(0.65, 1.25);
        cloud.speed = randomBetween(0.1, 0.24);
      }
    }

    for (const mark of groundMarks) {
      mark.x -= speed * dt;
      if (mark.x < -40) {
        const next = makeGroundMark();
        mark.x = W + randomBetween(0, 100);
        mark.y = next.y;
        mark.w = next.w;
        mark.h = next.h;
      }
    }

    for (const particle of particles) {
      particle.age += dt;
      particle.x += particle.vx * dt;
      particle.y += particle.vy * dt;
      particle.vy += 900 * dt;
    }
    particles = particles.filter((particle) => particle.age < particle.life);

    const nightTarget = Math.floor(score / 700) % 2;
    nightAlpha += (nightTarget - nightAlpha) * Math.min(1, dt * 2.4);

    updateScoreUi();
  }

  function drawCloud(cloud, p) {
    const x = Math.round(cloud.x);
    const y = Math.round(cloud.y);
    const s = cloud.scale;
    ctx.globalAlpha = 0.28 + nightAlpha * 0.18;
    ctx.fillStyle = p.muted;
    ctx.fillRect(x, y, Math.round(52 * s), Math.round(10 * s));
    ctx.fillRect(
      x + Math.round(11 * s),
      y - Math.round(8 * s),
      Math.round(28 * s),
      Math.round(9 * s)
    );
    ctx.fillRect(
      x + Math.round(7 * s),
      y + Math.round(10 * s),
      Math.round(36 * s),
      Math.round(6 * s)
    );
    ctx.globalAlpha = 1;
  }

  function drawStandingDino(p) {
    const x = Math.round(dino.x);
    const y = Math.round(dino.y);
    const phase = Math.floor(runTime * 11) % 2;
    const bodyY = y - 32;
    ctx.fillStyle = p.fg;
    ctx.fillRect(x - 8, bodyY + 2, 16, 8);
    ctx.fillRect(x - 3, bodyY + 10, 12, 7);
    ctx.fillRect(x + 5, bodyY, 31, 22);
    ctx.fillRect(x + 23, y - 48, 13, 20);
    ctx.fillRect(x + 25, y - 52, 20, 15);
    ctx.fillRect(x + 38, y - 42, 11, 8);
    ctx.fillRect(x + 30, y - 29, 13, 4);
    ctx.fillRect(x + 38, y - 25, 4, 5);
    if (phase === 0) {
      ctx.fillRect(x + 12, y - 16, 8, 13);
      ctx.fillRect(x + 9, y - 4, 15, 4);
      ctx.fillRect(x + 28, y - 13, 8, 9);
      ctx.fillRect(x + 28, y - 5, 12, 5);
    } else {
      ctx.fillRect(x + 12, y - 13, 8, 9);
      ctx.fillRect(x + 9, y - 5, 13, 5);
      ctx.fillRect(x + 28, y - 16, 8, 13);
      ctx.fillRect(x + 29, y - 4, 15, 4);
    }
    ctx.fillStyle = p.bg;
    ctx.fillRect(x + 41, y - 49, 4, 4);
    ctx.fillRect(x + 44, y - 37, 5, 2);
  }

  function drawDuckingDino(p) {
    const x = Math.round(dino.x);
    const y = Math.round(dino.y);
    const phase = Math.floor(runTime * 12) % 2;
    ctx.fillStyle = p.fg;
    ctx.fillRect(x - 8, y - 24, 14, 8);
    ctx.fillRect(x - 2, y - 29, 46, 18);
    ctx.fillRect(x + 34, y - 36, 17, 16);
    ctx.fillRect(x + 48, y - 30, 10, 7);
    ctx.fillRect(x + 40, y - 20, 14, 5);
    if (phase === 0) {
      ctx.fillRect(x + 10, y - 13, 9, 10);
      ctx.fillRect(x + 7, y - 4, 15, 4);
      ctx.fillRect(x + 30, y - 11, 8, 8);
      ctx.fillRect(x + 30, y - 4, 12, 4);
    } else {
      ctx.fillRect(x + 10, y - 10, 9, 7);
      ctx.fillRect(x + 7, y - 4, 13, 4);
      ctx.fillRect(x + 30, y - 13, 8, 10);
      ctx.fillRect(x + 31, y - 4, 15, 4);
    }
    ctx.fillStyle = p.bg;
    ctx.fillRect(x + 48, y - 33, 4, 4);
  }

  function drawDino(p) {
    if (dino.ducking && dino.onGround) {
      drawDuckingDino(p);
    } else {
      drawStandingDino(p);
    }
  }

  function drawCactus(obstacle, p) {
    const x = Math.round(obstacle.x);
    const y = Math.round(obstacle.y);
    const w = obstacle.w;
    const h = obstacle.h;
    const trunkW = Math.max(9, Math.round(w * 0.38));
    const trunkX = x + Math.round((w - trunkW) / 2);
    ctx.fillStyle = p.fg;
    ctx.fillRect(trunkX, y + 3, trunkW, h - 3);
    ctx.fillRect(x + 1, y + Math.round(h * 0.34), 5, Math.round(h * 0.3));
    ctx.fillRect(
      x + 1,
      y + Math.round(h * 0.34),
      Math.round(w * 0.36),
      5
    );
    if (obstacle.variant !== 1) {
      ctx.fillRect(x + w - 6, y + Math.round(h * 0.46), 5, Math.round(h * 0.25));
      ctx.fillRect(
        x + Math.round(w * 0.54),
        y + Math.round(h * 0.46),
        Math.round(w * 0.4),
        5
      );
    }
    ctx.fillStyle = p.bg;
    ctx.globalAlpha = 0.25;
    ctx.fillRect(trunkX + 2, y + 9, 2, h - 15);
    ctx.globalAlpha = 1;
  }

  function drawBird(obstacle, p) {
    const x = Math.round(obstacle.x);
    const y = Math.round(obstacle.y);
    const flap = Math.floor(runTime * 9) % 2;
    ctx.fillStyle = p.fg;
    ctx.fillRect(x + 12, y + 15, 30, 10);
    ctx.fillRect(x + 35, y + 8, 13, 11);
    ctx.fillRect(x + 46, y + 12, 8, 4);
    ctx.fillRect(x + 2, y + 13, 13, 6);
    if (flap === 0) {
      ctx.fillRect(x + 16, y + 1, 19, 14);
      ctx.fillRect(x + 37, y + 3, 8, 8);
    } else {
      ctx.fillRect(x + 16, y + 24, 19, 10);
      ctx.fillRect(x + 24, y + 20, 10, 6);
    }
    ctx.fillStyle = p.bg;
    ctx.fillRect(x + 40, y + 10, 3, 3);
  }

  function drawObstacles(p) {
    for (const obstacle of obstacles) {
      if (obstacle.type === "bird") {
        drawBird(obstacle, p);
      } else {
        drawCactus(obstacle, p);
      }
    }
  }

  function drawParticles() {
    for (const particle of particles) {
      const alpha = 1 - particle.age / particle.life;
      ctx.globalAlpha = Math.max(0, alpha);
      ctx.fillStyle = particle.color;
      ctx.fillRect(
        Math.round(particle.x),
        Math.round(particle.y),
        Math.round(particle.size),
        Math.round(particle.size)
      );
    }
    ctx.globalAlpha = 1;
  }

  function drawStars(p) {
    if (nightAlpha < 0.02) {
      return;
    }
    ctx.fillStyle = p.fg;
    for (const star of stars) {
      const twinkle = 0.55 + 0.45 * Math.sin(runTime * 2 + star.phase);
      ctx.globalAlpha = nightAlpha * twinkle;
      ctx.fillRect(star.x, star.y, star.size, star.size);
    }
    ctx.globalAlpha = 1;
  }

  function drawScore(p) {
    const current = String(score).padStart(5, "0");
    const best = String(highScore).padStart(5, "0");
    ctx.fillStyle = p.fg;
    ctx.font = `700 24px ${MONO}`;
    ctx.textAlign = "right";
    ctx.textBaseline = "top";
    ctx.fillText(`HI ${best}  ${current}`, W - 30, 28);
    ctx.textAlign = "left";
  }

  function draw() {
    const p = palette();
    ctx.fillStyle = p.bg;
    ctx.fillRect(0, 0, W, H);
    drawStars(p);

    for (const cloud of clouds) {
      drawCloud(cloud, p);
    }

    ctx.fillStyle = p.fg;
    ctx.fillRect(0, GROUND_Y, W, 2);
    ctx.globalAlpha = 0.45;
    for (const mark of groundMarks) {
      ctx.fillRect(
        Math.round(mark.x),
        Math.round(mark.y),
        Math.round(mark.w),
        mark.h
      );
    }
    ctx.globalAlpha = 1;

    drawObstacles(p);
    drawParticles();
    drawDino(p);
    drawScore(p);
  }

  function frame(timestamp) {
    const dt = Math.min(0.05, Math.max(0, (timestamp - lastFrame) / 1000));
    lastFrame = timestamp;
    if (state === "running") {
      update(dt);
    }
    draw();
    requestAnimationFrame(frame);
  }

  async function loadScores() {
    lbStatus.textContent = "載入中…";
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 4000);
    try {
      const response = await fetch("/api/scores?limit=10", {
        cache: "no-store",
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error("bad status");
      }
      const data = await response.json();
      renderScores(data.scores || []);
      renderStats(data.stats);
      lbStatus.textContent = data.scores && data.scores.length
        ? "即時同步 SQLite 排行榜"
        : "目前還沒有紀錄";
      setOnline(true);
    } catch (error) {
      lbStatus.textContent = "離線中，排行榜暫時無法載入（遊戲仍可玩）";
      setOnline(false);
    } finally {
      window.clearTimeout(timer);
    }
  }

  function renderScores(scores) {
    lbList.replaceChildren();
    if (!scores.length) {
      const empty = document.createElement("li");
      empty.className = "lb-empty";
      empty.textContent = "目前沒有紀錄，當第一個吧！";
      lbList.append(empty);
      return;
    }
    for (const entry of scores) {
      const item = document.createElement("li");
      const name = document.createElement("span");
      name.className = "lb-name";
      name.textContent = entry.name;
      name.title = entry.created_at || "";
      const points = document.createElement("span");
      points.className = "lb-score";
      points.textContent = String(entry.score);
      item.append(name, points);
      lbList.append(item);
    }
  }

  function renderStats(stats) {
    lbStats.replaceChildren();
    if (!stats) {
      return;
    }
    const items = [
      ["場次", stats.games],
      ["最高", stats.best],
      ["平均", stats.average],
    ];
    for (const [label, value] of items) {
      const wrapper = document.createElement("span");
      const text = document.createElement("b");
      text.textContent = String(value);
      wrapper.append(label, text);
      lbStats.append(wrapper);
    }
  }

  async function submitScore() {
    if (saveUsed) {
      return;
    }
    const name = nameInput.value.trim();
    if (!name) {
      saveMsg.textContent = "請先輸入名字。";
      nameInput.focus();
      return;
    }
    if (name.length > 16) {
      saveMsg.textContent = "名字最多 16 個字。";
      return;
    }
    saveBtn.disabled = true;
    saveBtn.textContent = "送出中…";
    saveMsg.textContent = "";
    try {
      const response = await fetch("/api/scores", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, score }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "送出失敗");
      }
      writeStorage(STORAGE.name, name);
      saveUsed = true;
      saveBtn.textContent = "已送出";
      saveMsg.textContent = `已存入排行榜，目前第 ${data.rank} 名。`;
      setOnline(true);
      showToast(`分數已送出，目前排名第 ${data.rank} 名`);
      await loadScores();
    } catch (error) {
      saveBtn.disabled = false;
      saveBtn.textContent = "重試送出";
      saveMsg.textContent = "無法連線到排行榜，分數仍保留在本機最高分。";
      setOnline(false);
    }
  }

  document.addEventListener("keydown", (event) => {
    const tag = document.activeElement ? document.activeElement.tagName : "";
    if (tag === "INPUT" || tag === "TEXTAREA") {
      return;
    }
    if (event.code === "Space" || event.code === "ArrowUp" || event.code === "KeyW") {
      event.preventDefault();
      if (!event.repeat) {
        jumpOrStart();
      }
    } else if (event.code === "ArrowDown" || event.code === "KeyS") {
      event.preventDefault();
      setDuck(true);
    } else if (event.code === "KeyP" || event.code === "Escape") {
      event.preventDefault();
      togglePause();
    } else if (event.code === "KeyR") {
      if (state === "over") {
        startGame();
      }
    } else if (event.code === "KeyM") {
      toggleSound();
    }
  });

  document.addEventListener("keyup", (event) => {
    if (event.code === "ArrowDown" || event.code === "KeyS") {
      setDuck(false);
    }
  });

  canvas.addEventListener(
    "pointerdown",
    (event) => {
      event.preventDefault();
      jumpOrStart();
    },
    { passive: false }
  );

  jumpBtn.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    jumpOrStart();
  });

  duckBtn.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    setDuck(true);
  });

  for (const type of ["pointerup", "pointercancel", "pointerleave"]) {
    duckBtn.addEventListener(type, () => setDuck(false));
  }

  startBtn.addEventListener("click", () => {
    if (state === "paused") {
      resumeGame();
    } else {
      startGame();
    }
  });

  pauseBtn.addEventListener("click", togglePause);
  restartBtn.addEventListener("click", startGame);
  refreshBtn.addEventListener("click", loadScores);
  saveBtn.addEventListener("click", submitScore);

  nameInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      submitScore();
    }
  });

  function toggleSound() {
    muted = !muted;
    writeStorage(STORAGE.muted, muted ? "1" : "0");
    updateSoundButton();
    if (!muted) {
      beep(620, 0.06, "square", 0.02);
      showToast("音效已開啟");
    } else {
      showToast("音效已關閉");
    }
  }

  soundBtn.addEventListener("click", toggleSound);

  document.addEventListener("visibilitychange", () => {
    if (document.hidden && state === "running") {
      pauseGame();
    }
  });

  window.addEventListener("online", () => {
    loadScores();
  });

  window.addEventListener("offline", () => {
    setOnline(false);
  });

  window.__dinoRun = {
    version: "1.0.0",
    snapshot() {
      return {
        state,
        score,
        highScore,
        speed,
        distance,
        nightAlpha,
        obstacles: obstacles.length,
        dino: {
          x: dino.x,
          y: dino.y,
          vy: dino.vy,
          onGround: dino.onGround,
          ducking: dino.ducking,
        },
      };
    },
  };

  if ("serviceWorker" in navigator && /^https?:$/.test(window.location.protocol)) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("./sw.js").catch(() => {});
    });
  }

  initClouds();
  initGroundMarks();
  initStars();
  updateSoundButton();
  updatePauseButton();
  updateScoreUi();
  showOverlay("ready");
  loadScores();
  lastFrame = performance.now();
  requestAnimationFrame(frame);
})();
