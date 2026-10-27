/* ============================================================
   CTIS-EEG Web 客户端逻辑
   - 单页应用：首页 / 设备 / 训练 / 记录
   - 五大认知任务 + 退出训练机制
============================================================ */

const API = "";  // 同域
const SEQ_TASKS = ["orient", "memencode", "trailblink", "semflow", "nameblink"];
const SEQ_REST_SEC = 5;
const state = {
    currentUser: null,
    currentTask: null,
    currentTaskName: "",
    currentScene: null,
    trials: [],
    currentTrialIdx: 0,
    correctCount: 0,
    taskStartTime: 0,   // 整个任务开始时间
    trialStartTime: 0,  // 当前trial开始时间
    startTime: 0,
    difficulty: "L2",
    highlightIdx: 0,
    highlightTimer: null,
    blinkTimer: null,
    awaitingBlink: false,
    eegHistory: [],
    eegTimer: null,
    deviceTimer: null,
    sequential: false,
    seqIndex: 0,
    seqResults: [],
    seqRestTimer: null,
    eegMode: false,  // true=脑电眨眼控制, false=鼠标控制
    submitting: false,  // 防重复提交
    // EEG实时指标
    eegAlpha: 0,
    eegTheta: 0,
    eegDelta: 0,
    eegBeta: 0,
    eegGamma: 0,
    eegBlinkCount: 0,
    eegBlinkWindowStart: 0,
    eegCfi: 0,
    eegAi: 0,
};

/* ============== 通用工具 ============== */
function $(id) { return document.getElementById(id); }

var _toastThrottle = {};
function showToast(msg, type = "info") {
    // 节流：相同消息3秒内不重复弹出
    var key = msg + type;
    if (_toastThrottle[key]) return;
    _toastThrottle[key] = true;
    setTimeout(function() { delete _toastThrottle[key]; }, 3000);

    const el = document.createElement("div");
    el.className = "toast " + type;
    el.textContent = msg;
    $("toastContainer").appendChild(el);
    setTimeout(() => el.remove(), 2400);
}

function switchPage(name) {
    if (!state.currentUser && name !== "home") {
        showToast("请先登录", "error");
        return;
    }
    document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
    document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
    $("page-" + name).classList.add("active");
    var tabBtn = document.querySelector('.nav-tab[data-page="' + name + '"]');
    if (tabBtn) tabBtn.classList.add("active");
    if (name === "train") loadTaskList();
    if (name === "records") loadRecords();
    if (name === "trajectory") loadTrajectory();
    if (name === "home") refreshHomeStats();
    if (name === "profile") loadProfile();
    if (name === "qbank") initQbank();
}

document.addEventListener("click", function(e) {
    var tab = e.target.closest(".nav-tab");
    if (tab && tab.dataset.page) {
        e.preventDefault();
        switchPage(tab.dataset.page);
    }
});

/* ============== 认证与用户管理 ============== */
function getToken() { return localStorage.getItem("ctis_token"); }
function setToken(t) { localStorage.setItem("ctis_token", t); }
function clearToken() { localStorage.removeItem("ctis_token"); localStorage.removeItem("ctis_user"); }
function getStoredUser() { try { return JSON.parse(localStorage.getItem("ctis_user")); } catch(e) { return null; } }
function setStoredUser(u) { localStorage.setItem("ctis_user", JSON.stringify(u)); }

function authHeaders() {
    var t = getToken();
    return t ? {"Authorization": "Bearer " + t} : {};
}

function showAuthLogin() {
    $("authLoginForm").style.display = "block";
    $("authRegisterForm").style.display = "none";
}
function showAuthRegister() {
    $("authLoginForm").style.display = "none";
    $("authRegisterForm").style.display = "block";
}

async function doLogin() {
    var name = $("loginName").value.trim();
    var pw = $("loginPassword").value.trim();
    if (!name || !pw) { showToast("请输入用户名和密码", "error"); return; }
    try {
        var res = await fetch(API + "/api/auth/login", {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({name: name, password: pw})
        });
        var data = await res.json();
        if (data.ok) {
            setToken(data.token);
            setStoredUser(data.user);
            state.currentUser = data.user;
            onLoginSuccess();
            showToast("登录成功，欢迎 " + name, "success");
        } else {
            showToast(data.msg || "登录失败", "error");
        }
    } catch(e) { showToast("网络错误: " + e.message, "error"); }
}

async function doRegister() {
    var name = $("regName").value.trim();
    var pw = $("regPassword").value.trim();
    if (!name || !pw) { showToast("请输入用户名和密码", "error"); return; }
    if (pw.length < 4) { showToast("密码至少4位", "error"); return; }
    try {
        var res = await fetch(API + "/api/auth/register", {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                name: name, password: pw,
                age: parseInt($("regAge").value) || 0,
                gender: $("regGender").value.trim(),
                diagnosis: $("regDiagnosis").value.trim(),
                phone: $("regPhone").value.trim(),
                education: $("regEducation").value.trim(),
            })
        });
        var data = await res.json();
        if (data.ok) {
            setToken(data.token);
            setStoredUser(data.user);
            state.currentUser = data.user;
            onLoginSuccess();
            showToast("注册成功，欢迎 " + name, "success");
        } else {
            showToast(data.msg || "注册失败", "error");
        }
    } catch(e) { showToast("网络错误: " + e.message, "error"); }
}

function onLoginSuccess() {
    $("authOverlay").style.display = "none";
    $("userChip").style.display = "flex";
    $("userAvatar").textContent = state.currentUser.name[0] || "U";
    $("userChipName").textContent = state.currentUser.name;
    $("homeGreeting").textContent = "您好，" + state.currentUser.name;
    refreshHomeStats();
}

function doLogout() {
    state.currentUser = null;
    clearToken();
    $("authOverlay").style.display = "flex";
    $("userChip").style.display = "none";
    showAuthLogin();
    $("loginName").value = "";
    $("loginPassword").value = "";
    showToast("已退出登录", "info");
}

async function tryAutoLogin() {
    var token = getToken();
    var user = getStoredUser();
    if (!token || !user) {
        $("authOverlay").style.display = "flex";
        return;
    }
    try {
        var res = await fetch(API + "/api/auth/me", {headers: authHeaders()});
        var data = await res.json();
        if (data.ok) {
            state.currentUser = data.user;
            setStoredUser(data.user);
            onLoginSuccess();
        } else {
            clearToken();
            $("authOverlay").style.display = "flex";
        }
    } catch(e) {
        // 网络不通时用缓存用户
        state.currentUser = user;
        onLoginSuccess();
    }
}

async function loadProfile() {
    if (!state.currentUser) return;
    var u = state.currentUser;
    $("profileName").value = u.name || "";
    $("profileAge").value = u.age || "";
    $("profileGender").value = u.gender || "";
    $("profileDiagnosis").value = u.diagnosis || "";
    $("profilePhone").value = u.phone || "";
    $("profileEducation").value = u.education || "";
    $("profileMedicalHistory").value = u.medical_history || "";
    $("profileEmergencyContact").value = u.emergency_contact || "";
    $("profileUserId").textContent = u.user_id || "--";
    $("profileCreatedAt").textContent = u.created_at ? u.created_at.slice(0, 10) : "--";
}

async function saveProfile() {
    var data = {
        age: parseInt($("profileAge").value) || 0,
        gender: $("profileGender").value.trim(),
        diagnosis: $("profileDiagnosis").value.trim(),
        phone: $("profilePhone").value.trim(),
        education: $("profileEducation").value.trim(),
        medical_history: $("profileMedicalHistory").value.trim(),
        emergency_contact: $("profileEmergencyContact").value.trim(),
    };
    try {
        var res = await fetch(API + "/api/auth/profile", {
            method: "PUT",
            headers: Object.assign({"Content-Type": "application/json"}, authHeaders()),
            body: JSON.stringify(data)
        });
        var result = await res.json();
        if (result.ok) {
            state.currentUser = result.user;
            setStoredUser(result.user);
            showToast("个人信息已保存", "success");
        } else {
            showToast(result.msg || "保存失败", "error");
        }
    } catch(e) { showToast("网络错误", "error"); }
}

async function changePassword() {
    var oldPw = $("oldPassword").value.trim();
    var newPw = $("newPassword").value.trim();
    var confirmPw = $("confirmPassword").value.trim();
    if (!oldPw || !newPw || !confirmPw) { showToast("请填写完整", "error"); return; }
    if (newPw !== confirmPw) { showToast("两次新密码不一致", "error"); return; }
    if (newPw.length < 4) { showToast("新密码至少4位", "error"); return; }
    try {
        var res = await fetch(API + "/api/auth/change-password", {
            method: "POST",
            headers: Object.assign({"Content-Type": "application/json"}, authHeaders()),
            body: JSON.stringify({old_password: oldPw, new_password: newPw})
        });
        var data = await res.json();
        if (data.ok) {
            showToast("密码修改成功", "success");
            $("oldPassword").value = "";
            $("newPassword").value = "";
            $("confirmPassword").value = "";
        } else {
            showToast(data.msg, "error");
        }
    } catch(e) { showToast("网络错误", "error"); }
}

async function refreshHomeStats() {
    if (!state.currentUser) return;
    try {
        var results = await Promise.all([
            fetch(API + "/api/stats/" + state.currentUser.user_id),
            fetch(API + "/api/sequential_sessions?user_id=" + state.currentUser.user_id)
        ]);
        var statsData = await results[0].json();
        var seqData = await results[1].json();

        var sessionCount = (seqData.ok && seqData.groups) ? seqData.groups.length : 0;
        var totalScoreAll = 0;
        var totalTrialsAll = 0;
        var totalCorrectAll = 0;
        if (seqData.ok && seqData.groups) {
            seqData.groups.forEach(function(g) {
                g.items.forEach(function(it) {
                    totalScoreAll += (it.score || 0);
                    totalTrialsAll += (it.trial_count || 0);
                    totalCorrectAll += (it.correct_count || 0);
                });
            });
        }
        var avgScore = sessionCount ? (totalScoreAll / sessionCount) : 0;
        var avgAcc = totalTrialsAll ? Math.round(totalCorrectAll / totalTrialsAll * 100) : 0;

        $("homeTotalSessions").textContent = sessionCount;
        $("homeTotalTrials").textContent = totalTrialsAll;
        $("homeAvgScore").textContent = avgScore.toFixed(1);
        $("homeAccuracy").textContent = avgAcc + "%";
    } catch(e) {}
}

/* ============== 设备连接 ============== */
$("deviceMode").addEventListener("change", function(e) {
    $("portRow").style.display = e.target.value === "serial" ? "block" : "none";
});

async function connectDevice() {
    const mode = $("deviceMode").value;
    const port = $("devicePort").value.trim();
    const res = await fetch(API + "/api/device/connect", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({mode: mode, port: port})
    });
    const data = await res.json();
    if (data.ok) {
        showToast(data.msg, "success");
        startDevicePolling();
    } else {
        showToast(data.msg, "error");
    }
}

async function disconnectDevice() {
    await fetch(API + "/api/device/disconnect", {method: "POST"});
    showToast("已断开", "info");
    stopDevicePolling();
    state.eegMode = false;
    refreshDeviceStatus({connected: false, mode: "disconnected", eeg_value: 0, signal_quality: 0, thresholds: {}});
}

async function runCalibration() {
    const res = await fetch(API + "/api/device/calibrate", {method: "POST"});
    const data = await res.json();
    if (data.ok) {
        showToast("校准完成", "success");
    }
}

function startDevicePolling() {
    stopDevicePolling();
    state.deviceTimer = setInterval(async function() {
        const res = await fetch(API + "/api/device/status");
        const data = await res.json();
        refreshDeviceStatus(data);
    }, 800);
}

function stopDevicePolling() {
    if (state.deviceTimer) clearInterval(state.deviceTimer);
    state.deviceTimer = null;
}

function refreshDeviceStatus(data) {
    const dot = $("statusDot");
    const txt = $("statusText");
    const mode = $("statusMode");
    var wasEeg = state.eegMode;
    if (data.connected) {
        dot.classList.add("connected");
        txt.textContent = "已连接";
        mode.textContent = data.mode === "sim" ? "模拟模式" : "串口 " + (data.port || "");
        $("signalQuality").textContent = data.signal_quality;
        $("eegValue").textContent = data.eeg_value;
        $("uptime").textContent = data.uptime_sec;
        pushEegPoint(data.eeg_value);
        state.eegMode = true;

        // 更新 EEG 实时指标 (EMA平滑)
        var alpha = 0.3;  // 平滑系数，越小越平滑
        state.eegAlpha = state.eegAlpha * (1 - alpha) + (data.alpha_power || 0) * alpha;
        state.eegTheta = state.eegTheta * (1 - alpha) + (data.theta_power || 0) * alpha;
        state.eegDelta = state.eegDelta * (1 - alpha) + (data.delta_power || 0) * alpha;
        state.eegBeta = state.eegBeta * (1 - alpha) + (data.beta_power || 0) * alpha;
        state.eegGamma = state.eegGamma * (1 - alpha) + (data.gamma_power || 0) * alpha;
        state.eegBlinkCount = state.eegBlinkCount * (1 - alpha) + (data.blink_rate || 0) * alpha;
        state.eegAi = state.eegAi * (1 - alpha) + (data.ai_value || 0) * alpha;
        state.eegCfi = state.eegCfi * (1 - alpha) + (data.cfi_value || 0) * alpha;

        // 更新右上角 EEG 面板
        $("eegPanelAlpha").textContent = state.eegAlpha.toFixed(1);
        $("eegPanelTheta").textContent = state.eegTheta.toFixed(1);
        var taRatio = state.eegAlpha > 0.01 ? (state.eegTheta / state.eegAlpha) : 0;
        $("eegPanelTA").textContent = taRatio.toFixed(2);
        $("eegPanelBlink").textContent = state.eegBlinkCount.toFixed(1);
        $("eegPanelAI").textContent = state.eegAi.toFixed(1);
        $("eegPanelCFI").textContent = state.eegCfi.toFixed(1);

        // CFI 颜色指示
        var cfiEl = $("eegPanelCFI");
        cfiEl.className = "eeg-value";
        if (state.eegCfi < 30) cfiEl.classList.add("eeg-cfi-low");
        else if (state.eegCfi < 60) cfiEl.classList.add("eeg-cfi-mid");
        else cfiEl.classList.add("eeg-cfi-high");

        // 显示 EEG 面板
        $("eegPanel").style.display = "block";
    } else {
        dot.classList.remove("connected");
        txt.textContent = "未连接";
        mode.textContent = "设备离线";
        state.eegMode = false;

        // 隐藏 EEG 面板
        $("eegPanel").style.display = "none";
    }
    // 更新导航栏控制模式指示
    updateControlModeUI();
    if (wasEeg !== state.eegMode) {
        showToast(state.eegMode ? "已切换为脑电眨眼控制" : "已切换为鼠标控制", "info");
    }
}

/* 更新导航栏控制模式指示器 */
function updateControlModeUI() {
    var chip = $("controlModeChip");
    var dot = $("controlModeDot");
    var label = $("controlModeLabel");
    if (state.eegMode) {
        chip.classList.add("eeg-mode");
        label.textContent = "脑电控制";
    } else {
        chip.classList.remove("eeg-mode");
        label.textContent = "鼠标控制";
    }
}

function pushEegPoint(v) {
    state.eegHistory.push(v);
    if (state.eegHistory.length > 200) state.eegHistory.shift();
    drawEegWave();
}

function drawEegWave() {
    const canvas = $("eegCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    const data = state.eegHistory;
    if (data.length < 2) return;

    // 绘制参数
    var padL = 36, padR = 8, padT = 8, padB = 18;
    var plotW = w - padL - padR;
    var plotH = h - padT - padB;
    var midY = padT + plotH / 2;

    // Y轴范围：自适应，但保证最小范围
    var maxAbs = Math.max(200, Math.max.apply(null, data.map(function(v) { return Math.abs(v); })));
    var yRange = maxAbs * 1.1;

    // 绘制背景网格
    ctx.strokeStyle = "rgba(176,137,104,0.12)";
    ctx.lineWidth = 0.5;
    // 水平网格线 (5条)
    for (var gi = 0; gi <= 4; gi++) {
        var gy = padT + (plotH / 4) * gi;
        ctx.beginPath();
        ctx.moveTo(padL, gy);
        ctx.lineTo(w - padR, gy);
        ctx.stroke();
    }
    // 垂直网格线 (6条)
    for (var gi = 0; gi <= 5; gi++) {
        var gx = padL + (plotW / 5) * gi;
        ctx.beginPath();
        ctx.moveTo(gx, padT);
        ctx.lineTo(gx, padT + plotH);
        ctx.stroke();
    }

    // Y轴标注
    ctx.fillStyle = "rgba(100,80,60,0.5)";
    ctx.font = "9px sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    var yLabels = [yRange, yRange/2, 0, -yRange/2, -yRange];
    for (var gi = 0; gi <= 4; gi++) {
        var gy = padT + (plotH / 4) * gi;
        ctx.fillText(yLabels[gi].toFixed(0), padL - 4, gy);
    }

    // X轴标注 (时间)
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    var totalSec = (data.length * 0.8 / 1000).toFixed(1);  // 0.8s轮询间隔
    for (var gi = 0; gi <= 5; gi++) {
        var gx = padL + (plotW / 5) * gi;
        var tLabel = ((data.length * 0.8 / 1000) * gi / 5).toFixed(1) + "s";
        ctx.fillText(tLabel, gx, padT + plotH + 3);
    }

    // 零线
    ctx.strokeStyle = "rgba(176,137,104,0.3)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padL, midY);
    ctx.lineTo(w - padR, midY);
    ctx.stroke();

    // 绘制波形 - 渐变填充
    ctx.beginPath();
    data.forEach(function(v, i) {
        var x = padL + (i / (data.length - 1)) * plotW;
        var y = midY - (v / yRange) * (plotH / 2);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    // 闭合填充区域
    var lastX = padL + plotW;
    ctx.lineTo(lastX, midY);
    ctx.lineTo(padL, midY);
    ctx.closePath();
    var grad = ctx.createLinearGradient(0, padT, 0, padT + plotH);
    grad.addColorStop(0, "rgba(176,137,104,0.15)");
    grad.addColorStop(0.5, "rgba(176,137,104,0.02)");
    grad.addColorStop(1, "rgba(176,137,104,0.15)");
    ctx.fillStyle = grad;
    ctx.fill();

    // 绘制波形线
    ctx.beginPath();
    data.forEach(function(v, i) {
        var x = padL + (i / (data.length - 1)) * plotW;
        var y = midY - (v / yRange) * (plotH / 2);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = "#B08968";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // 眨眼尖峰高亮标记
    data.forEach(function(v, i) {
        if (Math.abs(v) > 150) {
            var x = padL + (i / (data.length - 1)) * plotW;
            var y = midY - (v / yRange) * (plotH / 2);
            ctx.beginPath();
            ctx.arc(x, y, 3, 0, Math.PI * 2);
            ctx.fillStyle = "rgba(244,67,54,0.7)";
            ctx.fill();
        }
    });
}

/* ============== 任务列表 ============== */
var TASK_ICONS = {
    orient: "\u{1F9ED}", memencode: "\u{1F9E9}", trailblink: "\u{1F517}",
    semflow: "\u{1F43E}", nameblink: "\u{1F4D6}"
};

async function loadTaskList() {
    const res = await fetch(API + "/api/tasks");
    const data = await res.json();
    const container = $("taskList");
    container.innerHTML = "";
    var descMap = {
        orient: "时间/地点/人物定向问答，强化主动检索与更新能力",
        memencode: "编码-延迟-回忆三阶段词语记忆训练",
        trailblink: "数字-字母交替连线，训练执行功能与序列控制",
        semflow: "图像识别-语义分类-语义联想，分级激活语义网络",
        nameblink: "物体图片命名+梯度提示，训练命名与词汇检索",
    };
    data.tasks.forEach(function(t) {
        const card = document.createElement("div");
        card.className = "task-card";
        card.innerHTML =
            '<div class="task-icon">' + (TASK_ICONS[t.key] || "\u{1F3AF}") + '</div>' +
            '<div class="task-name">' + t.name + '</div>' +
            '<div class="task-desc">' + (descMap[t.key] || t.description) + '</div>' +
            '<div class="task-meta">' +
                '<span class="badge">' + t.scene_count + ' 套题库</span>' +
                '<span>随机抽题</span>' +
            '</div>';
        card.onclick = function() { startTask(t.key, t.name); };
        container.appendChild(card);
    });
}

/* ============== 训练流程 ============== */
async function startTask(taskKey, taskName) {
    if (!state.currentUser) { showToast("请先在首页选择用户", "error"); switchPage("home"); return; }
    state.currentTask = taskKey;
    state.currentTaskName = taskName;
    state.trials = [];
    state.currentTrialIdx = 0;
    state.correctCount = 0;
    state.taskStartTime = Date.now();
    state.trialStartTime = Date.now();
    state.startTime = Date.now();
    state.sequential = false;

    const res = await fetch(API + "/api/tasks/" + taskKey + "/scene?user_id=" + (state.currentUser ? state.currentUser.user_id : ""));
    const data = await res.json();
    if (!data.ok) { showToast("题库加载失败", "error"); return; }
    state.currentScene = data.scene;

    $("taskListContainer").style.display = "none";
    $("sequentialEntry").style.display = "none";
    $("sequentialStage").style.display = "none";
    $("taskStage").style.display = "block";
    $("taskStageName").textContent = taskName;
    $("taskStage").scrollIntoView({behavior: "smooth"});
    $("eegPanel").classList.add("training-active");
    runNextTrial();
}

function exitTask() {
    stopBlinkSimulation();
    stopHighlight();
    if (state.seqRestTimer) { clearInterval(state.seqRestTimer); state.seqRestTimer = null; }
    $("taskListContainer").style.display = "block";
    $("sequentialEntry").style.display = "block";
    $("taskStage").style.display = "none";
    $("sequentialStage").style.display = "none";
    $("eegPanel").classList.remove("training-active");
    var wasSequential = state.sequential;
    state.currentTask = null;
    state.currentScene = null;
    state.sequential = false;
    showToast(wasSequential ? "已退出顺序训练" : "已退出训练", "info");
    if (wasSequential && state.seqResults.length) {
        showSequentialSummary(state.seqResults, true);
        state.seqResults = [];
    }
}

/* ============== 顺序训练 ============== */
async function startSequential() {
    if (!state.currentUser) {
        showToast("请先登录", "error");
        return;
    }
    state.sequential = true;
    state.seqIndex = 0;
    state.seqResults = [];
    state.taskStartTime = Date.now();
    state.trialStartTime = Date.now();
    state.startTime = Date.now();

    $("taskListContainer").style.display = "none";
    $("sequentialEntry").style.display = "none";
    $("taskStage").style.display = "none";
    $("sequentialStage").style.display = "block";
    $("sequentialStage").scrollIntoView({behavior: "smooth"});
    $("eegPanel").classList.add("training-active");
    await runSequentialStep();
}

async function runSequentialStep() {
    if (!state.sequential) return;
    if (state.seqIndex >= SEQ_TASKS.length) {
        showSequentialSummary(state.seqResults, false);
        $("sequentialStage").style.display = "none";
        $("taskListContainer").style.display = "block";
        $("sequentialEntry").style.display = "block";
        state.sequential = false;
        return;
    }

    var taskKey = SEQ_TASKS[state.seqIndex];
    var taskName = taskNameOf(taskKey);
    state.currentTask = taskKey;
    state.currentTaskName = taskName;
    $("seqStageName").textContent = "顺序训练 · " + taskName;
    state.trials = [];
    state.currentTrialIdx = 0;
    state.correctCount = 0;
    state.trailErrors = 0;
    state.submitting = false;
    state.taskStartTime = Date.now();
    state.trialStartTime = Date.now();
    state.startTime = Date.now();

    var stage = $("sequentialStageContent");
    var stepsHtml = "";
    for (var si = 0; si < SEQ_TASKS.length; si++) {
        var cls = si < state.seqIndex ? "done" : (si === state.seqIndex ? "active" : "");
        var label = si < state.seqIndex ? "\u2713" : (si + 1);
        stepsHtml += '<div class="seq-step ' + cls + '">' + label + '</div>';
    }
    stage.innerHTML =
        '<div class="seq-progress"><div class="seq-step-row">' + stepsHtml + '</div></div>' +
        '<div class="seq-current-task">第 <b>' + (state.seqIndex + 1) + '</b> / ' + SEQ_TASKS.length + ' 项：<b>' + taskName + '</b></div>' +
        '<div class="task-prompt">题目加载中...</div>';

    var res = await fetch(API + "/api/tasks/" + taskKey + "/scene?user_id=" + (state.currentUser ? state.currentUser.user_id : ""));
    var data = await res.json();
    if (!data.ok || !state.sequential) { showToast("题库加载失败", "error"); return; }
    state.currentScene = data.scene;
    runNextTrialInSequential();
}

function runNextTrial() {
    var scene = state.currentScene;
    if (!scene) { finishTask(true); return; }
    if (state.currentTrialIdx >= scene.trials.length) { finishTask(true); return; }
    var trial = scene.trials[state.currentTrialIdx];
    renderTrial(trial);
}

function runNextTrialInSequential() {
    var scene = state.currentScene;
    if (!state.sequential) return;
    if (state.currentTrialIdx >= scene.trials.length) {
        finishSequentialStep();
        return;
    }
    renderSequentialTrial(scene.trials[state.currentTrialIdx]);
}

function buildStepsHtml() {
    var html = "";
    for (var i = 0; i < SEQ_TASKS.length; i++) {
        var cls = i < state.seqIndex ? "done" : (i === state.seqIndex ? "active" : "");
        var label = i < state.seqIndex ? "\u2713" : (i + 1);
        html += '<div class="seq-step ' + cls + '">' + label + '</div>';
    }
    return html;
}

function renderTrial(trial) {
    var stage = $("taskStageContent");
    var total = state.currentScene.trials.length;
    var idx = state.currentTrialIdx;
    var phase = trial.phase || "default";

    // 根据任务类型选择渲染方式
    if (phase === "encode") {
        renderEncodeTrial(stage, trial, total, idx);
    } else if (phase === "delay") {
        renderDelayTrial(stage, trial, total, idx);
    } else if (phase === "recall") {
        renderRecallTrial(stage, trial, total, idx);
    } else if (phase === "trail") {
        renderTrailTrial(stage, trial, total, idx);
    } else if (phase === "digit_span") {
        renderDigitSpanTrial(stage, trial, total, idx);
    } else if (phase === "serial_seven") {
        renderSerialSevenTrial(stage, trial, total, idx);
    } else if (phase === "module_a") {
        renderNamingTrial(stage, trial, total, idx);
    } else if (phase === "module_b") {
        renderFluencyTrial(stage, trial, total, idx);
    } else if (phase === "module_c") {
        renderSimilarityTrial(stage, trial, total, idx);
    } else if (phase === "name") {
        renderNameTrial(stage, trial, total, idx);
    } else if (phase === "repetition") {
        renderRepetitionTrial(stage, trial, total, idx);
    } else {
        renderDefaultTrial(stage, trial, total, idx);
    }
}

function renderSequentialTrial(trial) {
    var stage = $("sequentialStageContent");
    var total = state.currentScene.trials.length;
    var idx = state.currentTrialIdx;
    var phase = trial.phase || "default";

    // 顺序训练中额外显示步骤指示器
    var stepsPrefix =
        '<div class="seq-progress"><div class="seq-step-row">' + buildStepsHtml() + '</div></div>' +
        '<div class="seq-current-task">第 <b>' + (state.seqIndex + 1) + '</b> / ' + SEQ_TASKS.length + ' 项：<b>' + state.currentTaskName + '</b></div>';

    if (phase === "encode") {
        renderEncodeTrial(stage, trial, total, idx, stepsPrefix);
    } else if (phase === "delay") {
        renderDelayTrial(stage, trial, total, idx, stepsPrefix);
    } else if (phase === "recall") {
        renderRecallTrial(stage, trial, total, idx, stepsPrefix);
    } else if (phase === "trail") {
        renderTrailTrial(stage, trial, total, idx, stepsPrefix);
    } else if (phase === "digit_span") {
        renderDigitSpanTrial(stage, trial, total, idx, stepsPrefix);
    } else if (phase === "serial_seven") {
        renderSerialSevenTrial(stage, trial, total, idx, stepsPrefix);
    } else if (phase === "module_a") {
        renderNamingTrial(stage, trial, total, idx, stepsPrefix);
    } else if (phase === "module_b") {
        renderFluencyTrial(stage, trial, total, idx, stepsPrefix);
    } else if (phase === "module_c") {
        renderSimilarityTrial(stage, trial, total, idx, stepsPrefix);
    } else if (phase === "name") {
        renderNameTrial(stage, trial, total, idx, stepsPrefix);
    } else if (phase === "repetition") {
        renderRepetitionTrial(stage, trial, total, idx, stepsPrefix);
    } else {
        renderDefaultTrial(stage, trial, total, idx, stepsPrefix);
    }
}

/* 通用进度条+信息 */
function trialHeader(total, idx, prefix) {
    return (prefix || "") +
        '<div class="task-progress"><div class="task-progress-bar" style="width:' + (idx / total * 100) + '%;"></div></div>' +
        '<div class="task-scene-info">题套: ' + (state.currentScene.set_name || "") + '  ·  第' + (idx + 1) + ' / ' + total + ' 题</div>';
}

/* ===== 定向力(orient) 默认渲染 ===== */
function renderDefaultTrial(stage, trial, total, idx, prefix) {
    var optsHtml = "";
    var options = trial.options || [];
    options.forEach(function(o, i) {
        optsHtml += '<div class="option" data-idx="' + i + '">' + o + '</div>';
    });
    var imageHtml = "";
    if (trial.image) {
        imageHtml = '<div class="task-image" style="text-align:center; font-size:64px; margin:16px 0; line-height:1.2;">' + trial.image + '</div>';
    }
    var ctrlHint = state.eegMode ? '\u{1F441} 注视高亮选项，然后<b>强眨眼</b>确认' : '\u{1F5B1} 点击选项确认答案';
    stage.innerHTML =
        trialHeader(total, idx, prefix) +
        imageHtml +
        '<div class="task-prompt">' + trial.prompt + '</div>' +
        '<div class="options" id="optionsBox">' + optsHtml + '</div>' +
        '<div class="task-stats"><span>正确: ' + state.correctCount + '/' + idx + '</span><span>' + ctrlHint + '</span></div>';
    bindOptions();
    startScanningHighlight();
    startBlinkSimulation(trial);
}

/* ===== 情景记忆 - 编码阶段 ===== */
function renderEncodeTrial(stage, trial, total, idx, prefix) {
    var ctrlHint = state.eegMode ? '\u{1F441} 眨眼选择信心等级' : '\u{1F5B1} 点击选择信心等级';
    var roundInfo = trial.encode_round ? '（第' + trial.encode_round + '次学习）' : '';
    stage.innerHTML =
        trialHeader(total, idx, prefix) +
        '<div class="task-phase-label" style="text-align:center; color:var(--accent); font-weight:700; font-size:14px; margin-bottom:8px;">[ 编码阶段 ]' + roundInfo + '</div>' +
        '<div class="task-encode-word" style="text-align:center; font-size:48px; font-weight:800; color:var(--primary); margin:24px 0;">' + trial.word + '</div>' +
        '<div class="task-prompt" style="text-align:center;">' + trial.prompt + '</div>' +
        '<div class="options" id="optionsBox">' +
            '<div class="option" data-idx="0">记住了(强)</div>' +
            '<div class="option" data-idx="1">不太确定(弱)</div>' +
            '<div class="option" data-idx="2">没记住</div>' +
        '</div>' +
        '<div class="task-stats"><span>编码: ' + (idx + 1) + ' / ' + total + '</span><span>' + ctrlHint + '</span></div>';
    bindOptions();
    startScanningHighlight();
    startBlinkSimulation(trial);
}

/* ===== 情景记忆 - 延迟阶段 ===== */
function renderDelayTrial(stage, trial, total, idx, prefix) {
    var optsHtml = "";
    var options = trial.options || [];
    options.forEach(function(o, i) {
        optsHtml += '<div class="option" data-idx="' + i + '">' + o + '</div>';
    });
    var ctrlHint = state.eegMode ? '\u{1F441} 眨眼选择答案' : '\u{1F5B1} 点击选择答案';
    stage.innerHTML =
        trialHeader(total, idx, prefix) +
        '<div class="task-phase-label" style="text-align:center; color:var(--accent); font-weight:700; font-size:14px; margin-bottom:8px;">[ 延迟阶段 - 回答问题 ]</div>' +
        '<div class="task-prompt">' + trial.prompt + '</div>' +
        '<div class="options" id="optionsBox">' + optsHtml + '</div>' +
        '<div class="task-stats"><span>延迟问题</span><span>' + ctrlHint + '</span></div>';
    bindOptions();
    startScanningHighlight();
    startBlinkSimulation(trial);
}

/* ===== 情景记忆 - 回忆阶段 ===== */
function renderRecallTrial(stage, trial, total, idx, prefix) {
    var ctrlHint = state.eegMode ? '\u{1F441} 眨眼选择' : '\u{1F5B1} 点击选择';
    stage.innerHTML =
        trialHeader(total, idx, prefix) +
        '<div class="task-phase-label" style="text-align:center; color:var(--accent); font-weight:700; font-size:14px; margin-bottom:8px;">[ 回忆阶段 ]</div>' +
        '<div class="task-encode-word" style="text-align:center; font-size:42px; font-weight:700; color:var(--primary-dark); margin:24px 0;">' + trial.word + '</div>' +
        '<div class="task-prompt" style="text-align:center;">' + trial.prompt + '</div>' +
        '<div class="options" id="optionsBox">' +
            '<div class="option" data-idx="0">出现过</div>' +
            '<div class="option" data-idx="1">没出现过</div>' +
        '</div>' +
        '<div class="task-stats"><span>回忆: ' + (idx + 1) + '/' + total + '</span><span>' + ctrlHint + '</span></div>';
    bindOptions();
    startScanningHighlight();
    startBlinkSimulation(trial);
}

/* ===== 执行功能 - 连线 (对齐标准TMT) ===== */
function renderTrailTrial(stage, trial, total, idx, prefix) {
    var markers = trial.markers || [];
    var gs = trial.grid_size || 4;
    var targetOrder = trial.target_order;

    // SVG连线网格
    var svgW = 360, svgH = 360;
    var cellW = svgW / gs, cellH = svgH / gs;
    var markerR = 22;

    // 计算标记中心坐标
    function markerCenter(m) {
        return { x: m.col * cellW + cellW / 2, y: m.row * cellH + cellH / 2 };
    }

    // 绘制已完成的连线（实线绿色）
    var linesHtml = "";
    var doneMarkers = markers.filter(function(m) { return m.order < targetOrder; });
    doneMarkers.sort(function(a, b) { return a.order - b.order; });
    for (var i = 1; i < doneMarkers.length; i++) {
        var p1 = markerCenter(doneMarkers[i - 1]);
        var p2 = markerCenter(doneMarkers[i]);
        linesHtml += '<line x1="' + p1.x + '" y1="' + p1.y + '" x2="' + p2.x + '" y2="' + p2.y + '" stroke="#6A994E" stroke-width="3" stroke-linecap="round"/>';
    }

    // 绘制标记圆圈 - 标准TMT：所有未完成节点外观相同，不提示目标
    var circlesHtml = "";
    markers.forEach(function(m) {
        var c = markerCenter(m);
        var isDone = m.order < targetOrder;
        var fill, stroke, sw, textColor, fontSize;

        if (isDone) {
            fill = "#6A994E"; stroke = "#4a7a33"; sw = 2; textColor = "white"; fontSize = 16;
        } else {
            // 标准TMT：所有未完成节点外观一致，不区分目标
            fill = "#FAF6F0"; stroke = "#B08968"; sw = 2; textColor = "#3D2C1E"; fontSize = 16;
        }

        circlesHtml += '<circle cx="' + c.x + '" cy="' + c.y + '" r="' + markerR + '" fill="' + fill + '" stroke="' + stroke + '" stroke-width="' + sw + '"' +
            (isDone ? '' : ' data-order="' + m.order + '" class="trail-node" style="cursor:pointer;"') +
            '/>';
        circlesHtml += '<text x="' + c.x + '" y="' + (c.y + 5) + '" text-anchor="middle" fill="' + textColor + '" font-size="' + fontSize + '" font-weight="700" font-family="sans-serif" pointer-events="none">' + m.label + '</text>';

        // 已完成的序号标记
        if (isDone) {
            circlesHtml += '<text x="' + (c.x + markerR - 4) + '" y="' + (c.y - markerR + 8) + '" text-anchor="middle" fill="#6A994E" font-size="10" font-weight="700" font-family="sans-serif">✓</text>';
        }
    });

    // 不添加目标脉冲动画（标准TMT不提示目标位置）

    var svgHtml = '<svg id="trailSvg" width="' + svgW + '" height="' + svgH + '" viewBox="0 0 ' + svgW + ' ' + svgH + '" style="display:block; margin:16px auto; background:var(--bg-soft); border-radius:12px;">' +
        linesHtml + circlesHtml +
        '</svg>';

    var ctrlHint = state.eegMode ? '\u{1F441} 注视高亮标记，眨眼确认选择' : '\u{1F5B1} 点击正确的下一个节点完成连线';
    stage.innerHTML =
        trialHeader(total, idx, prefix) +
        '<div class="task-phase-label" style="text-align:center; color:var(--accent); font-weight:700; font-size:14px; margin-bottom:8px;">[ 连线训练 ]</div>' +
        '<div class="task-prompt" style="text-align:center;">' + trial.prompt + '</div>' +
        svgHtml +
        '<div class="task-stats"><span>步骤: ' + (targetOrder + 1) + '/' + markers.length + '</span><span>错误: <b id="trailErrorCount">' + (state.trailErrors || 0) + '</b></span><span>' + ctrlHint + '</span></div>';

    // === 连线交互逻辑 (标准TMT：用户自己找下一个节点) ===
    var svgEl = document.getElementById("trailSvg");
    if (!svgEl) return;

    // 获取所有未完成节点
    var nodeCircles = svgEl.querySelectorAll("circle.trail-node");

    // EEG扫描：轮流高亮未完成节点
    var scanIdx = 0;
    var SCAN_INTERVAL = 2000;

    function clearAllHighlights() {
        nodeCircles.forEach(function(c) {
            c.setAttribute("stroke", "#B08968");
            c.setAttribute("stroke-width", "2");
            c.style.filter = "";
        });
    }

    function highlightNode(idx) {
        clearAllHighlights();
        var c = nodeCircles[idx];
        if (c) {
            c.setAttribute("stroke", "#FFD700");
            c.setAttribute("stroke-width", "4");
            c.style.filter = "drop-shadow(0 0 10px rgba(255,215,0,0.7))";
        }
    }

    // 启动EEG扫描（仅EEG模式下可见高亮扫描）
    if (state.eegMode) {
        highlightNode(0);
        if (state.trailScanTimer) clearInterval(state.trailScanTimer);
        state.trailScanTimer = setInterval(function() {
            scanIdx = (scanIdx + 1) % nodeCircles.length;
            highlightNode(scanIdx);
        }, SCAN_INTERVAL);
    }

    // 选择节点：判断是否为正确顺序
    function selectNode(circleEl) {
        var order = parseInt(circleEl.getAttribute("data-order"));
        var isCorrect = (order === targetOrder);

        if (isCorrect) {
            // 正确：停止扫描，提交答案
            if (state.trailScanTimer) { clearInterval(state.trailScanTimer); state.trailScanTimer = null; }
            submitAnswer(0, 2);
        } else {
            // 错误：红色闪烁反馈
            if (!state.trailErrors) state.trailErrors = 0;
            state.trailErrors++;
            var origFill = circleEl.getAttribute("fill");
            var origStroke = circleEl.getAttribute("stroke");
            var origSw = circleEl.getAttribute("stroke-width");
            circleEl.setAttribute("fill", "#E07A5F");
            circleEl.setAttribute("stroke", "#B5524B");
            circleEl.setAttribute("stroke-width", "3");
            circleEl.style.filter = "drop-shadow(0 0 8px rgba(224,122,95,0.6))";
            setTimeout(function() {
                circleEl.setAttribute("fill", origFill);
                circleEl.setAttribute("stroke", origStroke);
                circleEl.setAttribute("stroke-width", origSw);
                circleEl.style.filter = "";
            }, 600);
            showToast("顺序错误！请找到正确的下一个节点", "error");
            var errSpan = document.getElementById("trailErrorCount");
            if (errSpan) errSpan.textContent = state.trailErrors;
        }
    }

    // 鼠标点击：直接点击节点选择
    nodeCircles.forEach(function(c) {
        c.addEventListener("click", function() {
            if (state.submitting) return;
            selectNode(c);
        });
    });

    // EEG模式：眨眼确认当前高亮节点
    stopBlinkSimulation();
    if (state.eegMode) {
        state.awaitingBlink = true;
        var blinkTick = function() {
            if (!state.awaitingBlink || !state.currentTask) return;
            // 眨眼 = 确认当前高亮的节点
            var highlightedCircle = nodeCircles[scanIdx];
            if (highlightedCircle) {
                selectNode(highlightedCircle);
            }
            // 如果没有提交成功（错误选择），继续等待
            if (state.awaitingBlink) {
                var next = 1500 + Math.random() * 1000;
                state.blinkTimer = setTimeout(blinkTick, next);
            }
        };
        state.blinkTimer = setTimeout(blinkTick, 1800);
    }
}

/* ===== 执行功能 - 数字倒背 (对齐MoCA注意力) ===== */
function renderDigitSpanTrial(stage, trial, total, idx, prefix) {
    var digits = trial.digits || "";
    var digitArr = digits.split("-");
    var ctrlHint = state.eegMode ? '\u{1F441} 眨眼选择倒背结果' : '\u{1F5B1} 点击选择倒背结果';

    // 数字逐个展示动画
    var digitCardsHtml = "";
    digitArr.forEach(function(d, i) {
        digitCardsHtml += '<div class="digit-span-card" style="display:inline-block; width:56px; height:64px; line-height:64px; text-align:center; font-size:32px; font-weight:800; color:var(--primary); background:var(--bg-soft); border:2px solid var(--border); border-radius:10px; margin:4px; animation:digitPop 0.3s ease ' + (i * 0.15) + 's both;">' + d + '</div>';
    });

    var optsHtml = "";
    var options = trial.options || [];
    options.forEach(function(o, i) {
        optsHtml += '<div class="option" data-idx="' + i + '">' + o + '</div>';
    });

    stage.innerHTML =
        trialHeader(total, idx, prefix) +
        '<div class="task-phase-label" style="text-align:center; color:var(--accent); font-weight:700; font-size:14px; margin-bottom:8px;">[ 数字倒背 ]</div>' +
        '<div class="task-prompt" style="text-align:center;">' + trial.prompt + '</div>' +
        '<div style="text-align:center; margin:20px 0;">' + digitCardsHtml + '</div>' +
        '<div style="text-align:center; margin:8px 0; font-size:15px; color:var(--text-soft);">请从右到左倒着选择数字序列</div>' +
        '<div class="options" id="optionsBox">' + optsHtml + '</div>' +
        '<div class="task-stats"><span>倒背: ' + (idx + 1) + '/' + total + '</span><span>' + ctrlHint + '</span></div>';

    // 添加数字弹出动画
    var style = document.getElementById("digitSpanStyle");
    if (!style) {
        style = document.createElement("style");
        style.id = "digitSpanStyle";
        style.textContent = "@keyframes digitPop { from { transform: scale(0.3); opacity:0; } to { transform: scale(1); opacity:1; } }";
        document.head.appendChild(style);
    }

    bindOptions();
    startScanningHighlight();
    startBlinkSimulation(trial);
}

/* ===== 执行功能 - 连续减7 (对齐MMSE注意计算) ===== */
function renderSerialSevenTrial(stage, trial, total, idx, prefix) {
    var startVal = trial.start || 100;
    var ctrlHint = state.eegMode ? '\u{1F441} 眨眼选择答案' : '\u{1F5B1} 点击选择答案';

    var optsHtml = "";
    var options = trial.options || [];
    options.forEach(function(o, i) {
        var isCorrect = (o === trial.correct_value);
        optsHtml += '<div class="option" data-idx="' + i + '">' + o + '</div>';
    });

    stage.innerHTML =
        trialHeader(total, idx, prefix) +
        '<div class="task-phase-label" style="text-align:center; color:var(--accent); font-weight:700; font-size:14px; margin-bottom:8px;">[ 连续减7 ]</div>' +
        '<div style="text-align:center; margin:20px 0;">' +
            '<div style="font-size:48px; font-weight:800; color:var(--primary);">' + startVal + '</div>' +
            '<div style="font-size:24px; color:var(--text-soft); margin:8px 0;">- 7 = ?</div>' +
        '</div>' +
        '<div class="task-prompt" style="text-align:center;">' + trial.prompt + '</div>' +
        '<div class="options" id="optionsBox">' + optsHtml + '</div>' +
        '<div class="task-stats"><span>减7: ' + (idx + 1) + '/' + total + '</span><span>' + ctrlHint + '</span></div>';

    bindOptions();
    startScanningHighlight();
    startBlinkSimulation(trial);
}

/* ===== 语义记忆 - 命名 (对齐MoCA命名3题) ===== */
function renderNamingTrial(stage, trial, total, idx, prefix) {
    var emoji = trial.emoji || "\u{1F4E6}";
    var optsHtml = "";
    var options = trial.options || [];
    options.forEach(function(o, i) {
        optsHtml += '<div class="option" data-idx="' + i + '">' + o + '</div>';
    });
    var ctrlHint = state.eegMode ? '\u{1F441} 眨眼选择正确名称' : '\u{1F5B1} 点击选择正确名称';

    stage.innerHTML =
        trialHeader(total, idx, prefix) +
        '<div class="task-phase-label" style="text-align:center; color:var(--accent); font-weight:700; font-size:14px; margin-bottom:8px;">[ 命名训练 ]</div>' +
        '<div style="text-align:center; margin:16px 0;">' +
            '<div style="font-size:80px; line-height:1.2;">' + emoji + '</div>' +
        '</div>' +
        '<div class="task-prompt" style="text-align:center;">' + trial.prompt + '</div>' +
        '<div class="options" id="optionsBox">' + optsHtml + '</div>' +
        '<div class="task-stats"><span>命名: ' + (idx + 1) + '/' + total + '</span><span>' + ctrlHint + '</span></div>';

    bindOptions();
    startScanningHighlight();
    startBlinkSimulation(trial);
}

/* ===== 语义记忆 - 语义流畅性 (对齐MoCA: 1分钟说出≥11个) ===== */
function renderFluencyTrial(stage, trial, total, idx, prefix) {
    var category = trial.category || "动物";
    var timeLimit = trial.time_limit_sec || 60;
    var threshold = trial.threshold || 11;
    var ctrlHint = state.eegMode ? '\u{1F441} 眨眼开始计时' : '\u{1F5B1} 点击开始计时';

    // 预设词汇池（根据类别）
    var wordPools = {
        "动物": ["猫","狗","鱼","鸟","马","兔子","老虎","海豚","牛","羊","鸡","鸭","猪","鹿","斑马","鲨鱼","熊","狐狸","松鼠","企鹅","海豹","猫头鹰","鲸鱼","鹰","蛇","海龟","大象","猴子","蝴蝶","蜜蜂","蚂蚁","蜗牛","螃蟹","龙虾","乌龟","鹦鹉","孔雀","鸽子","燕子","麻雀","狮子","豹子","狼","河马","长颈鹿","袋鼠","考拉","熊猫","鳄鱼","蜥蜴"],
        "蔬菜": ["白菜","萝卜","土豆","西红柿","黄瓜","茄子","青椒","豆角","菠菜","芹菜","韭菜","冬瓜","南瓜","丝瓜","苦瓜","生菜","莴笋","莲藕","蘑菇","木耳","花菜","西兰花","洋葱","大蒜","生姜","大葱","香菜","胡萝卜","红薯","山药","芋头","竹笋","豆芽","豇豆","毛豆","豌豆","蚕豆","油菜","芥菜","苋菜"],
        "城市": ["北京","上海","广州","深圳","成都","杭州","南京","武汉","重庆","西安","苏州","天津","长沙","郑州","东莞","青岛","沈阳","大连","厦门","福州","哈尔滨","济南","温州","宁波","昆明","贵阳","太原","合肥","南宁","乌鲁木齐","兰州","呼和浩特","海口","三亚","拉萨","银川","西宁","石家庄","长春","南昌"],
    };
    var pool = wordPools[category] || wordPools["动物"];

    // 从池中随机选20个作为候选词，混入5个干扰词
    var distractorPools = {
        "动物": ["苹果","桌子","汽车","电脑","电话"],
        "蔬菜": ["牛肉","飞机","钢琴","眼镜","字典"],
        "城市": ["黄河","泰山","长城","西湖","草原"],
    };
    var distractors = distractorPools[category] || ["苹果","桌子","汽车","电脑","电话"];

    // 随机选20个正确词 + 5个干扰词
    var shuffledPool = pool.slice().sort(function() { return Math.random() - 0.5; });
    var candidateWords = shuffledPool.slice(0, 20).concat(distractors);
    candidateWords.sort(function() { return Math.random() - 0.5; });

    stage.innerHTML =
        trialHeader(total, idx, prefix) +
        '<div class="task-phase-label" style="text-align:center; color:var(--accent); font-weight:700; font-size:14px; margin-bottom:8px;">[ 语义流畅性 ]</div>' +
        '<div class="task-prompt" style="text-align:center; font-size:18px; font-weight:600;">请在1分钟内选出所有<b style="color:var(--primary);">' + category + '</b></div>' +
        '<div style="text-align:center; margin:12px 0;">' +
            '<div id="fluencyTimer" style="font-size:48px; font-weight:800; color:var(--primary);">60</div>' +
            '<div style="font-size:14px; color:var(--text-soft);">剩余秒数</div>' +
        '</div>' +
        '<div id="fluencyWordGrid" style="display:flex; flex-wrap:wrap; gap:8px; justify-content:center; max-width:600px; margin:12px auto;">' +
            candidateWords.map(function(w) {
                var isDistractor = distractors.indexOf(w) >= 0;
                return '<div class="fluency-word-chip" data-word="' + w + '" data-distractor="' + (isDistractor ? "1" : "0") + '" style="display:inline-block; padding:8px 16px; border:2px solid var(--border); border-radius:20px; font-size:15px; cursor:pointer; transition:all 0.2s; user-select:none; background:var(--bg-card);">' + w + '</div>';
            }).join("") +
        '</div>' +
        '<div style="text-align:center; margin:8px 0;">' +
            '<span style="font-size:14px; color:var(--text-soft);">已选出: <b id="fluencyCount" style="color:var(--primary);">0</b> 个 · 达标: ≥' + threshold + '个</span>' +
        '</div>' +
        '<div class="options" id="optionsBox">' +
            '<div class="option" data-idx="0" id="fluencyStartBtn">开始计时</div>' +
        '</div>' +
        '<div class="task-stats"><span>流畅性</span><span>' + ctrlHint + '</span></div>';

    // 流畅性计时逻辑
    var selectedWords = [];
    var fluencyTimerInterval = null;
    var fluencyTimeLeft = timeLimit;
    var fluencyStarted = false;
    var correctCount = 0;
    var wrongCount = 0;

    // 词汇点选逻辑
    var wordChips = document.querySelectorAll(".fluency-word-chip");
    wordChips.forEach(function(chip) {
        chip.addEventListener("click", function() {
            if (!fluencyStarted) return;
            var word = chip.dataset.word;
            var isDistractor = chip.dataset.distractor === "1";
            if (chip.classList.contains("selected")) {
                // 取消选择
                chip.classList.remove("selected");
                chip.style.background = "var(--bg-card)";
                chip.style.borderColor = "var(--border)";
                chip.style.color = "var(--text)";
                var idx2 = selectedWords.indexOf(word);
                if (idx2 >= 0) selectedWords.splice(idx2, 1);
                if (isDistractor) wrongCount--;
                else correctCount--;
            } else {
                // 选择
                chip.classList.add("selected");
                if (isDistractor) {
                    chip.style.background = "rgba(181, 82, 75, 0.15)";
                    chip.style.borderColor = "var(--danger)";
                    chip.style.color = "var(--danger)";
                    wrongCount++;
                } else {
                    chip.style.background = "var(--primary)";
                    chip.style.borderColor = "var(--primary)";
                    chip.style.color = "white";
                    correctCount++;
                }
                selectedWords.push(word);
            }
            var countEl = document.getElementById("fluencyCount");
            if (countEl) countEl.textContent = correctCount;
        });
    });

    // 开始计时按钮
    var startBtn = document.getElementById("fluencyStartBtn");
    startBtn.addEventListener("click", function() {
        if (fluencyStarted) return;
        fluencyStarted = true;
        startBtn.textContent = "计时中...";
        startBtn.style.opacity = "0.6";

        fluencyTimerInterval = setInterval(function() {
            fluencyTimeLeft--;
            var timerEl = document.getElementById("fluencyTimer");
            if (timerEl) timerEl.textContent = fluencyTimeLeft;
            if (fluencyTimeLeft <= 0) {
                clearInterval(fluencyTimerInterval);
                // 时间到，计算流畅性得分并接入submitAnswer流程
                var fluencyCount = correctCount;
                trial.fluency_result = fluencyCount;
                trial.fluency_words = selectedWords.filter(function(w) { return distractors.indexOf(w) < 0; });
                // 流畅性评分: 达到threshold为满分(正确), 否则按比例
                var fluencyScore = Math.min(fluencyCount / threshold, 1);
                showToast("时间到！正确选出" + correctCount + "个" + category + (wrongCount > 0 ? "，误选" + wrongCount + "个" : ""), "info");
                // 通过submitAnswer记录结果: answer=0表示达标, answer=1表示未达标
                trial.answer = (fluencyCount >= threshold) ? 0 : 1;
                trial.options = ["达标(" + fluencyCount + "个)", "未达标(" + fluencyCount + "个)"];
                submitAnswer(trial.answer, 1);
            }
        }, 1000);
    });

    // EEG模式下也支持眨眼开始
    startScanningHighlight();
    startBlinkSimulation(trial);
}

/* ===== 语义记忆 - 相似性抽象 (对齐MoCA抽象思维) ===== */
function renderSimilarityTrial(stage, trial, total, idx, prefix) {
    var optsHtml = "";
    var options = trial.options || [];
    options.forEach(function(o, i) {
        optsHtml += '<div class="option" data-idx="' + i + '">' + o + '</div>';
    });
    var ctrlHint = state.eegMode ? '\u{1F441} 眨眼选择' : '\u{1F5B1} 点击选择';

    stage.innerHTML =
        trialHeader(total, idx, prefix) +
        '<div class="task-phase-label" style="text-align:center; color:var(--accent); font-weight:700; font-size:14px; margin-bottom:8px;">[ 相似性判断 ]</div>' +
        '<div class="task-prompt" style="text-align:center; font-size:17px; font-weight:600;">' + trial.prompt + '</div>' +
        '<div class="options" id="optionsBox">' + optsHtml + '</div>' +
        '<div class="task-stats"><span>抽象: ' + (idx + 1) + '/' + total + '</span><span>' + ctrlHint + '</span></div>';

    bindOptions();
    startScanningHighlight();
    startBlinkSimulation(trial);
}

/* ===== 命名能力 - 复述 (对齐MoCA语言复述) ===== */
function renderRepetitionTrial(stage, trial, total, idx, prefix) {
    var sentence = trial.sentence || "";
    var optsHtml = "";
    var options = trial.options || [];
    options.forEach(function(o, i) {
        optsHtml += '<div class="option" data-idx="' + i + '" style="font-size:14px; line-height:1.5; padding:12px 16px;">' + o + '</div>';
    });
    var ctrlHint = state.eegMode ? '\u{1F441} 眨眼选择完全一致的句子' : '\u{1F5B1} 点击选择完全一致的句子';

    stage.innerHTML =
        trialHeader(total, idx, prefix) +
        '<div class="task-phase-label" style="text-align:center; color:var(--accent); font-weight:700; font-size:14px; margin-bottom:8px;">[ 语言复述 ]</div>' +
        '<div style="text-align:center; margin:20px 0; padding:16px 24px; background:var(--bg-soft); border-radius:12px; border:2px solid var(--primary);">' +
            '<div style="font-size:13px; color:var(--text-soft); margin-bottom:8px;">请仔细阅读并记住这句话：</div>' +
            '<div style="font-size:20px; font-weight:700; color:var(--primary-dark); line-height:1.6;">"' + sentence + '"</div>' +
        '</div>' +
        '<div class="task-prompt" style="text-align:center;">请选择与原句完全一致的选项：</div>' +
        '<div class="options" id="optionsBox">' + optsHtml + '</div>' +
        '<div class="task-stats"><span>复述: ' + (idx + 1) + '/' + total + '</span><span>' + ctrlHint + '</span></div>';

    bindOptions();
    startScanningHighlight();
    startBlinkSimulation(trial);
}

/* ===== 语义记忆 - 子模块A 图像识别 ===== */
function renderSemATrial(stage, trial, total, idx, prefix) {
    var ctrlHint = state.eegMode ? '\u{1F441} 眨眼选择' : '\u{1F5B1} 点击选择';
    // 不显示名称！只显示emoji图片让用户判断
    stage.innerHTML =
        trialHeader(total, idx, prefix) +
        '<div class="task-phase-label" style="text-align:center; color:var(--accent); font-weight:700; font-size:14px; margin-bottom:8px;">[ 快速识别 ]</div>' +
        '<div class="task-encode-word" style="text-align:center; font-size:72px; margin:20px 0;">' + getAnimalEmoji(trial.item_name) + '</div>' +
        '<div class="task-prompt" style="text-align:center;">' + trial.prompt + '</div>' +
        '<div class="options" id="optionsBox">' +
            '<div class="option" data-idx="0">是动物</div>' +
            '<div class="option" data-idx="1">不是动物</div>' +
        '</div>' +
        '<div class="task-stats"><span>识别: ' + (idx + 1) + '/' + total + '</span><span>' + ctrlHint + '</span></div>';
    bindOptions();
    startScanningHighlight();
    startBlinkSimulation(trial);
}

/* ===== 语义记忆 - 子模块B 语义分类 ===== */
function renderSemBTrial(stage, trial, total, idx, prefix) {
    var optsHtml = "";
    var options = trial.options || [];
    options.forEach(function(o, i) {
        optsHtml += '<div class="option" data-idx="' + i + '">' + o + '</div>';
    });
    var ctrlHint = state.eegMode ? '\u{1F441} 眨眼选择类别' : '\u{1F5B1} 点击选择类别';
    // 不显示名称！只显示emoji图片让用户分类
    stage.innerHTML =
        trialHeader(total, idx, prefix) +
        '<div class="task-phase-label" style="text-align:center; color:var(--accent); font-weight:700; font-size:14px; margin-bottom:8px;">[ 语义分类 ]</div>' +
        '<div class="task-encode-word" style="text-align:center; font-size:72px; margin:16px 0;">' + getAnimalEmoji(trial.item_name) + '</div>' +
        '<div class="task-prompt" style="text-align:center;">这个动物属于哪一类？</div>' +
        '<div class="options" id="optionsBox">' + optsHtml + '</div>' +
        '<div class="task-stats"><span>分类: ' + (idx + 1) + '/' + total + '</span><span>' + ctrlHint + '</span></div>';
    bindOptions();
    startScanningHighlight();
    startBlinkSimulation(trial);
}

/* ===== 语义记忆 - 子模块C 语义联想 ===== */
function renderSemCTrial(stage, trial, total, idx, prefix) {
    var optsHtml = "";
    var options = trial.options || [];
    options.forEach(function(o, i) {
        optsHtml += '<div class="option" data-idx="' + i + '">' + o + '</div>';
    });
    var ctrlHint = state.eegMode ? '\u{1F441} 眨眼选择最相似的' : '\u{1F5B1} 点击选择最相似的';
    stage.innerHTML =
        trialHeader(total, idx, prefix) +
        '<div class="task-phase-label" style="text-align:center; color:var(--accent); font-weight:700; font-size:14px; margin-bottom:8px;">[ 语义联想 ]</div>' +
        '<div class="task-prompt">' + trial.prompt + '</div>' +
        '<div class="options" id="optionsBox">' + optsHtml + '</div>' +
        '<div class="task-stats"><span>联想: ' + (idx + 1) + '/' + total + '</span><span>' + ctrlHint + '</span></div>';
    bindOptions();
    startScanningHighlight();
    startBlinkSimulation(trial);
}

/* ===== 命名能力 - 物体图片命名 ===== */
function renderNameTrial(stage, trial, total, idx, prefix) {
    var emoji = trial.emoji || "\u{1F4E6}";
    var hintCategory = trial.hint_category || "";
    var hintInitial = trial.hint_initial || "";
    var ctrlHint = state.eegMode ? '\u{1F441} 眨眼选择正确名称' : '\u{1F5B1} 点击选择正确名称';

    // 渐进提示范式: 初始只显示emoji+描述，答错后逐步提示
    // hintLevel: 0=无提示, 1=类别提示, 2=首字提示
    var hintLevel = 0;
    var hintHtml = '<div id="hintArea"></div>';

    function buildOptsHtml() {
        var html = "";
        var options = trial.options || [];
        options.forEach(function(o, i) {
            html += '<div class="option" data-idx="' + i + '">' + o + '</div>';
        });
        return html;
    }

    function renderNameContent() {
        var hintAreaHtml = '';
        if (hintLevel === 1) {
            hintAreaHtml = '<div style="text-align:center; margin:10px 0; padding:10px 18px; background:#FFF8E1; border:2px dashed #D4A017; border-radius:10px; font-size:16px; color:#8B6914; font-weight:600;">提示：这是一类<b>' + hintCategory + '</b></div>';
        } else if (hintLevel === 2) {
            hintAreaHtml = '<div style="text-align:center; margin:10px 0; padding:10px 18px; background:#FFF8E1; border:2px dashed #D4A017; border-radius:10px; font-size:16px; color:#8B6914; font-weight:600;">提示：首字是<b style="font-size:24px;">' + hintInitial + '</b></div>';
        }

        stage.innerHTML =
            trialHeader(total, idx, prefix) +
            '<div class="task-phase-label" style="text-align:center; color:var(--accent); font-weight:700; font-size:14px; margin-bottom:8px;">[ 命名训练 ]' + (hintLevel > 0 ? ' · 提示等级' + hintLevel : '') + '</div>' +
            '<div style="text-align:center; margin:16px 0;">' +
                '<div style="font-size:80px; line-height:1.2;">' + emoji + '</div>' +
                '<div style="font-size:15px; color:var(--text-main); margin-top:10px; font-weight:600;">' + (trial.image_desc || "") + '</div>' +
            '</div>' +
            hintAreaHtml +
            '<div class="task-prompt" style="text-align:center;">' + trial.prompt + '</div>' +
            '<div class="options" id="optionsBox">' + buildOptsHtml() + '</div>' +
            '<div class="task-stats"><span>命名: ' + (idx + 1) + '/' + total + '</span><span>' + ctrlHint + '</span></div>';

        // 绑定选项点击
        bindNameOptions();
    }

    function bindNameOptions() {
        var optsBox = document.getElementById("optionsBox");
        if (optsBox) {
            if (state.eegMode) optsBox.classList.add("eeg-mode");
            else optsBox.classList.remove("eeg-mode");
        }
        document.querySelectorAll("#optionsBox .option").forEach(function(opt) {
            opt.onclick = function(e) {
                if (state.eegMode) {
                    e.preventDefault();
                    e.stopPropagation();
                    showToast("脑电控制模式下请使用眨眼确认", "info");
                    return;
                }
                var chosenIdx = parseInt(opt.dataset.idx);
                handleNameAnswer(chosenIdx);
            };
        });
    }

    function handleNameAnswer(chosenIdx) {
        var isCorrect = chosenIdx === trial.answer;
        if (isCorrect) {
            // 正确：记录提示等级并提交
            trial.hint_level_used = hintLevel;
            submitAnswer(chosenIdx, 1);
        } else {
            // 错误：渐进提示
            if (hintLevel === 0 && hintCategory) {
                hintLevel = 1;
                showToast("答案不正确，给您一个类别提示", "warning");
                renderNameContent();
            } else if (hintLevel === 1 && hintInitial) {
                hintLevel = 2;
                showToast("再给您一个首字提示", "warning");
                renderNameContent();
            } else {
                // 已到最高提示仍答错，记录并提交
                trial.hint_level_used = hintLevel;
                submitAnswer(chosenIdx, 1);
            }
        }
    }

    // 初始渲染
    renderNameContent();
    startScanningHighlight();

    // EEG模式下的眨眼处理需要覆盖默认submitAnswer逻辑
    // 存储handleNameAnswer到全局以便眨眼回调使用
    state._nameAnswerHandler = handleNameAnswer;
    startBlinkSimulation(trial);
}

/* 动物emoji映射 */
function getAnimalEmoji(name) {
    var map = {
        "猫": "\u{1F431}", "狗": "\u{1F436}", "鱼": "\u{1F41F}", "鸟": "\u{1F426}",
        "马": "\u{1F434}", "兔子": "\u{1F430}", "老虎": "\u{1F42F}", "海豚": "\u{1F42C}",
        "牛": "\u{1F42E}", "羊": "\u{1F411}", "鸡": "\u{1F414}", "鸭": "\u{1F986}",
        "猪": "\u{1F437}", "鹿": "\u{1F98C}", "斑马": "\u{1F993}", "鲨鱼": "\u{1F988}",
        "熊": "\u{1F43B}", "狐狸": "\u{1F98A}", "松鼠": "\u{1F98F}", "企鹅": "\u{1F427}",
        "海豹": "\u{1F9AD}", "猫头鹰": "\u{1F989}", "北极熊": "\u{1F43B}", "海象": "\u{1F9AD}",
        "狮子": "\u{1F981}", "鲸鱼": "\u{1F40B}", "鹰": "\u{1F985}", "蛇": "\u{1F40D}",
        "海龟": "\u{1F422}",
        "桌子": "\u{1F5BC}", "汽车": "\u{1F697}", "苹果": "\u{1F34E}", "书本": "\u{1F4D6}",
        "椅子": "\u{1FA91}", "石头": "\u{1FAA8}", "电视": "\u{1F4FA}", "帽子": "\u{1F452}",
        "香蕉": "\u{1F34C}", "雨伞": "\u{2602}", "杯子": "\u{1F964}", "枕头": "\u{1F6CF}",
        "沙发": "\u{1F6CB}", "眼镜": "\u{1F453}", "西瓜": "\u{1F349}", "书包": "\u{1F392}",
        "锅": "\u{1F373}", "毛巾": "\u{1F9F4}",
    };
    return map[name] || "\u{2753}";
}

/* 绑定选项点击：脑电模式下禁用鼠标，仅允许眨眼确认 */
function bindOptions() {
    var optsBox = document.getElementById("optionsBox");
    if (optsBox) {
        if (state.eegMode) optsBox.classList.add("eeg-mode");
        else optsBox.classList.remove("eeg-mode");
    }
    document.querySelectorAll("#optionsBox .option").forEach(function(opt) {
        opt.onclick = function(e) {
            if (state.eegMode) {
                e.preventDefault();
                e.stopPropagation();
                showToast("脑电控制模式下请使用眨眼确认", "info");
                return;
            }
            submitAnswer(parseInt(opt.dataset.idx));
        };
    });
}

/* 扫描高亮：每秒切到下一个选项 */
function startScanningHighlight() {
    stopHighlight();
    state.highlightIdx = 0;
    state.highlightTimer = setInterval(function() {
        var opts = document.querySelectorAll("#optionsBox .option");
        if (!opts.length) return;
        opts.forEach(function(o) { o.classList.remove("highlight"); });
        opts[state.highlightIdx % opts.length].classList.add("highlight");
        state.highlightIdx++;
    }, 1500);
}
function stopHighlight() {
    if (state.highlightTimer) clearInterval(state.highlightTimer);
    state.highlightTimer = null;
}

/* 模拟眨眼检测：仅在脑电模式下启动，周期性产生强眨眼事件 */
function startBlinkSimulation(trial) {
    stopBlinkSimulation();
    if (!state.eegMode) return;  // 非脑电模式不启动自动眨眼
    state.awaitingBlink = true;
    // 1.5-2.5s 随机产生一次强眨眼
    var tick = function() {
        if (!state.awaitingBlink || !state.currentTask) return;
        // 当某个选项正被高亮时，强眨眼视为确认
        var highlighted = document.querySelector("#optionsBox .option.highlight");
        if (highlighted) {
            var idx = parseInt(highlighted.dataset.idx);
            submitAnswer(idx, 2);  // intent_level=2 表示强眨眼
            return;
        }
        var next = 1500 + Math.random() * 1000;
        state.blinkTimer = setTimeout(tick, next);
    };
    state.blinkTimer = setTimeout(tick, 1800);
}

function stopBlinkSimulation() {
    state.awaitingBlink = false;
    if (state.blinkTimer) clearTimeout(state.blinkTimer);
    state.blinkTimer = null;
}

function submitAnswer(idx, intentLevel) {
    if (intentLevel === undefined) intentLevel = 1;
    // 防重复提交
    if (state.submitting) return;
    // 脑电模式下只接受眨眼提交(intentLevel=2)，拒绝鼠标点击
    if (state.eegMode && intentLevel !== 2) return;
    state.submitting = true;
    stopBlinkSimulation();
    stopHighlight();
    // 清理连线测试专用扫描定时器
    if (state.trailScanTimer) { clearInterval(state.trailScanTimer); state.trailScanTimer = null; }

    var trial = state.currentScene.trials[state.currentTrialIdx];
    // 编码阶段不判断对错，所有选项都视为"正确"（记录信心等级）
    var isEncode = (trial.phase === "encode");
    var correct = isEncode ? true : (idx === trial.answer);
    if (correct) state.correctCount++;
    var rt = Date.now() - state.trialStartTime;

    state.trials.push({
        trial_index: state.currentTrialIdx,
        prompt: trial.prompt,
        stimulus: trial.options[idx],
        is_correct: correct,
        intent_level: intentLevel,
        reaction_time_ms: rt,
        blink_type: intentLevel >= 2 ? "intentional" : (intentLevel === 1 ? "spontaneous" : "none"),
        alpha_power: Math.round(state.eegAlpha * 100) / 100,
        theta_power: Math.round(state.eegTheta * 100) / 100,
        delta_power: Math.round(state.eegDelta * 100) / 100,
        beta_power: Math.round(state.eegBeta * 100) / 100,
        gamma_power: Math.round(state.eegGamma * 100) / 100,
        cfi_snapshot: Math.round(state.eegCfi * 100) / 100,
        ai_snapshot: Math.round(state.eegAi * 100) / 100,
        fluency_result: trial.fluency_result || 0,
        fluency_words: trial.fluency_words || [],
    });

    // 反馈
    var opts = document.querySelectorAll("#optionsBox .option");
    if (isEncode) {
        // 编码阶段：显示信心等级确认，不显示对错
        opts.forEach(function(o, i) {
            o.onclick = null;
            if (i === idx) o.classList.add("correct");
        });
    } else {
        opts.forEach(function(o, i) {
            o.onclick = null;
            if (i === trial.answer) o.classList.add("correct");
            if (i === idx && !correct) o.classList.add("wrong");
        });
    }

    setTimeout(function() {
        state.submitting = false;
        state.currentTrialIdx++;
        state.trialStartTime = Date.now();
        state.startTime = Date.now();
        if (state.sequential) {
            runNextTrialInSequential();
        } else {
            runNextTrial();
        }
    }, correct ? 900 : 1400);
}

async function finishTask(completed) {
    stopBlinkSimulation();
    stopHighlight();
    $("eegPanel").classList.remove("training-active");
    $("taskListContainer").style.display = "block";
    $("sequentialEntry").style.display = "block";
    $("taskStage").style.display = "none";
    $("sequentialStage").style.display = "none";

    if (!state.currentUser || !state.currentTask) return;
    var totalTrials = state.trials.length;
    var duration = Math.round((Date.now() - state.taskStartTime) / 1000);
    // CT-30评分: 每项满分6分
    var score6 = computeTaskScore6(state.currentTask, state.correctCount, totalTrials, duration);

    // 单项训练不保存到数据库，仅显示总结
    showSummary(score6, state.correctCount, totalTrials, duration, completed);
}

/* 计算单项CT-30评分 (满分6分) */
function computeTaskScore6(taskKey, correct, total, durationSec) {
    var accuracy = total > 0 ? correct / total : 0;
    if (taskKey === "orient") {
        // 定向问答正确率 x 6
        return Math.round(accuracy * 6 * 100) / 100;
    } else if (taskKey === "memencode") {
        // 即刻回忆(2分) + 延迟回忆(3分) + 再认(1分)
        var encode2Correct = 0, encode2Total = 0;
        var recallCorrect = 0, recallTotal = 0;
        var recogCorrect = 0, recogTotal = 0;
        state.trials.forEach(function(tr) {
            var trial = state.currentScene.trials[tr.trial_index];
            if (!trial) return;
            if (trial.phase === "encode" && trial.encode_round === 2) {
                // 第2次编码正确数作为即刻回忆指标
                encode2Total++;
                if (tr.is_correct) encode2Correct++;
            } else if (trial.phase === "recall") {
                if (trial.is_target) {
                    // 目标词回忆
                    recallTotal++;
                    if (tr.is_correct) recallCorrect++;
                } else {
                    // 干扰词再认
                    recogTotal++;
                    if (tr.is_correct) recogCorrect++;
                }
            }
        });
        var immediateRate = encode2Total > 0 ? encode2Correct / encode2Total : 0;
        var recallRate = recallTotal > 0 ? recallCorrect / recallTotal : 0;
        var recogRate = recogTotal > 0 ? recogCorrect / recogTotal : 1;
        return Math.round((immediateRate * 2 + recallRate * 3 + recogRate * 1) * 100) / 100;
    } else if (taskKey === "trailblink") {
        // 连线正确率(4分) + 数字倒背(2分)
        // 连线：全对满分4分，全错0分，按正确率线性
        var trailCorrect = 0, trailTotal = 0;
        var spanCorrect = 0, spanTotal = 0;
        state.trials.forEach(function(tr) {
            var trial = state.currentScene.trials[tr.trial_index];
            if (!trial) return;
            if (trial.phase === "trail") {
                trailTotal++;
                if (tr.is_correct) trailCorrect++;
            } else if (trial.phase === "digit_span") {
                spanTotal++;
                if (tr.is_correct) spanCorrect++;
            }
        });
        var trailRate = trailTotal > 0 ? trailCorrect / trailTotal : 0;
        var spanRate = spanTotal > 0 ? spanCorrect / spanTotal : 0;
        return Math.round((trailRate * 4 + spanRate * 2) * 100) / 100;
    } else if (taskKey === "semflow") {
        // 命名正确(2分) + 语义流畅性(2分) + 相似性抽象(2分)
        var namingCorrect = 0, namingTotal = 0;
        var fluencyResult = 0, fluencyThreshold = 11;
        var simCorrect = 0, simTotal = 0;
        state.trials.forEach(function(tr) {
            var trial = state.currentScene.trials[tr.trial_index];
            if (!trial) return;
            if (trial.phase === "name") {
                namingTotal++;
                if (tr.is_correct) namingCorrect++;
            } else if (trial.phase === "fluency") {
                fluencyResult = trial.fluency_result || 0;
                fluencyThreshold = trial.threshold || 11;
            } else if (trial.phase === "similarity") {
                simTotal++;
                if (tr.is_correct) simCorrect++;
            }
        });
        var namingRate = namingTotal > 0 ? namingCorrect / namingTotal : 0;
        var fluencyRate = Math.min(fluencyResult / fluencyThreshold, 1);
        var simRate = simTotal > 0 ? simCorrect / simTotal : 0;
        return Math.round((namingRate * 2 + fluencyRate * 2 + simRate * 2) * 100) / 100;
    } else if (taskKey === "nameblink") {
        // 首次正确率(3分) + 渐进提示(2分) + 复述(1分)
        var nameCorrect = 0, nameTotal = 0, totalHints = 0;
        var repeatCorrect = 0, repeatTotal = 0;
        state.trials.forEach(function(tr) {
            var trial = state.currentScene.trials[tr.trial_index];
            if (!trial) return;
            if (trial.phase === "name") {
                nameTotal++;
                if (tr.is_correct) nameCorrect++;
                totalHints += (trial.hint_level_used || 0);
            } else if (trial.phase === "repetition") {
                repeatTotal++;
                if (tr.is_correct) repeatCorrect++;
            }
        });
        var firstRate = nameTotal > 0 ? nameCorrect / nameTotal : 0;
        var hintRate = nameTotal > 0 ? 1 - (totalHints / (nameTotal * 2)) : 1;  // 每题最多2级提示
        var repeatRate = repeatTotal > 0 ? repeatCorrect / repeatTotal : 0;
        return Math.round((firstRate * 3 + Math.max(0, hintRate) * 2 + repeatRate * 1) * 100) / 100;
    }
    return Math.round(accuracy * 6 * 100) / 100;
}

async function finishSequentialStep() {
    stopBlinkSimulation();
    stopHighlight();
    if (!state.sequential || !state.currentUser || !state.currentTask) return;

    var totalTrials = state.trials.length;
    var duration = Math.round((Date.now() - state.taskStartTime) / 1000);
    // CT-30评分: 每项满分6分
    var score6 = computeTaskScore6(state.currentTask, state.correctCount, totalTrials, duration);

    var cogMap = {orient: 0, memencode: 1, trailblink: 2, semflow: 3, nameblink: 4};
    var cog = [0, 0, 0, 0, 0];
    var cidx = cogMap[state.currentTask];
    if (cidx != null) cog[cidx] = state.correctCount / Math.max(1, totalTrials);

    // 顺序训练不逐项保存，只在最后汇总保存
    state.seqResults.push({
        task_key: state.currentTask,
        task_name: state.currentTaskName,
        total: totalTrials,
        correct: state.correctCount,
        score: score6,
        duration: duration,
        difficulty: state.difficulty,
        cog_vector: cog,
        trials: state.trials.slice(),
    });

    // 最后一项结束后直接进入总结
    if (state.seqIndex >= SEQ_TASKS.length - 1) {
        // 汇总保存到数据库
        await saveSequentialSession(state.seqResults);
        showSequentialSummary(state.seqResults, false);
        $("eegPanel").classList.remove("training-active");
        $("sequentialStage").style.display = "none";
        $("taskListContainer").style.display = "block";
        $("sequentialEntry").style.display = "block";
        state.sequential = false;
        return;
    }

    showRestCountdown(function() {
        state.seqIndex++;
        runSequentialStep();
    });
}

async function saveSequentialSession(results) {
    if (!state.currentUser || !results.length) return;
    var tasks = results.map(function(r, i) {
        return {
            task_key: r.task_key,
            difficulty: r.difficulty || 1,
            trial_count: r.total,
            correct_count: r.correct,
            score: r.score,
            duration_sec: r.duration,
            cog_vector: r.cog_vector || [0,0,0,0,0],
            trials: r.trials || [],
            group_order: i + 1,
        };
    });
    try {
        await fetch(API + "/api/sequential_session", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                user_id: state.currentUser.user_id,
                tasks: tasks,
            })
        });
        // 保存成功后清除轨迹缓存，确保下次加载最新数据
        _trajCache = null;
        // 如果当前在轨迹追踪页面，自动刷新
        if ($("page-trajectory").classList.contains("active")) {
            loadTrajectory();
        }
        // 如果当前在数据记录页面，自动刷新
        if ($("page-records").classList.contains("active")) {
            loadRecords();
        }
    } catch (e) {
        console.error("保存顺序训练会话失败", e);
    }
}

function showRestCountdown(onFinish) {
    var stage = $("sequentialStageContent");
    var remain = SEQ_REST_SEC;
    stage.innerHTML =
        '<div class="seq-rest-screen">' +
            '<div class="seq-progress"><div class="seq-step-row">' + buildStepsHtml() + '</div></div>' +
            '<div class="seq-current-task">刚刚完成: <b>' + state.currentTaskName + '</b></div>' +
            '<h3>请稍事休息</h3>' +
            '<div class="seq-countdown" id="restCountdown">' + remain + '</div>' +
            '<p class="text-soft" style="font-size:15px;">下一项即将开始: <b>' + taskNameOf(SEQ_TASKS[state.seqIndex + 1]) + '</b></p>' +
        '</div>';
    state.seqRestTimer = setInterval(function() {
        remain--;
        var el = $("restCountdown");
        if (el) el.textContent = remain;
        if (remain <= 0) {
            clearInterval(state.seqRestTimer);
            state.seqRestTimer = null;
            onFinish();
        }
    }, 1000);
}

function showSequentialSummary(results, exited) {
    // CT-30评分: 每项满分6分，总分30分
    var totalScore6 = results.reduce(function(s, r) { return s + r.score; }, 0);
    var totalScore6Round = Math.round(totalScore6 * 100) / 100;
    var totalCorrect = results.reduce(function(s, r) { return s + r.correct; }, 0);
    var totalTrials = results.reduce(function(s, r) { return s + r.total; }, 0);
    var totalDuration = results.reduce(function(s, r) { return s + r.duration; }, 0);

    $("summaryOverlay").style.display = "flex";
    $("summaryTitle").textContent = exited ? "顺序训练已退出" : "CT-30 认知训练完成";
    $("summaryEmoji").textContent = totalScore6Round >= 24 ? "\u{1F3C6}" : totalScore6Round >= 18 ? "\u{1F44D}" : "\u{1F4AA}";
    $("summaryMsg").textContent = exited
        ? "已完成" + results.length + " / " + SEQ_TASKS.length + " 项训练"
        : "CT-30 总分: " + totalScore6Round + " / 30 分";
    $("sumScore").textContent = totalScore6Round + "/30";
    $("sumCorrect").textContent = totalCorrect + "/" + totalTrials;
    $("sumDuration").textContent = totalDuration + "s";

    // 注入子任务明细 (每项6分制)
    var detail = document.getElementById("seqDetail");
    if (!detail) {
        detail = document.createElement("div");
        detail.id = "seqDetail";
        detail.style.cssText = "text-align:left; margin-top:16px; padding:12px; background:var(--bg-soft); border-radius:10px; font-size:14px; max-height:220px; overflow-y:auto;";
        document.querySelector(".summary-card").appendChild(detail);
    }
    var detailHtml = '<div style="font-weight:700; margin-bottom:8px; color:var(--primary);">CT-30 分项得分 (每项满分6分)</div>';
    results.forEach(function(r, i) {
        var bar = Math.round(r.score / 6 * 100);
        detailHtml +=
            '<div style="padding:6px 0; border-bottom:1px solid var(--border);">' +
                '<div style="display:flex; justify-content:space-between;">' +
                    '<span>' + (i + 1) + '. ' + r.task_name + '</span>' +
                    '<span style="color:var(--primary); font-weight:600;">' + r.score + ' / 6 分</span>' +
                '</div>' +
                '<div style="background:var(--border); border-radius:4px; height:6px; margin-top:4px;">' +
                    '<div style="background:var(--primary); border-radius:4px; height:6px; width:' + bar + '%;"></div>' +
                '</div>' +
            '</div>';
    });
    detailHtml += '<div style="text-align:right; font-weight:700; margin-top:8px; font-size:16px; color:var(--primary-dark);">CT-30 总分: ' + totalScore6Round + ' / 30</div>';
    detail.innerHTML = detailHtml;
}

function showSummary(score, correct, total, duration, completed) {
    $("summaryOverlay").style.display = "flex";
    $("summaryTitle").textContent = completed ? "训练完成" : "训练已退出";
    $("summaryEmoji").textContent = score >= 5 ? "\u{1F31F}" : score >= 3 ? "\u{1F44D}" : "\u{1F4AA}";
    $("summaryMsg").textContent = score >= 5 ? "非常棒！继续保持。" : "不要灰心，再来一次会更好。";
    $("sumScore").textContent = score + "/6";
    $("sumCorrect").textContent = correct + "/" + total;
    $("sumDuration").textContent = duration + "s";
}

function closeSummary(toHome) {
    $("summaryOverlay").style.display = "none";
    // 清除当前任务状态，避免关闭总结后意外重启训练
    state.currentTask = null;
    state.currentScene = null;
    if (toHome) switchPage("home");
}

/* ============== 数据记录 ============== */
async function loadRecords() {
    if (!state.currentUser) {
        $("recordsSubtitle").textContent = "请先在首页选择用户";
        $("sessionList").innerHTML = '<div class="empty-state"><div class="empty-emoji">\u{1F464}</div>请先选择用户</div>';
        return;
    }
    $("recordsSubtitle").textContent = "用户: " + state.currentUser.name;

    var results = await Promise.all([
        fetch(API + "/api/stats/" + state.currentUser.user_id),
        fetch(API + "/api/sequential_sessions?user_id=" + state.currentUser.user_id),
    ]);
    var statsData = await results[0].json();
    var seqData = await results[1].json();

    // 训练会话数 = 列表中的会话记录个数
    var sessionCount = (seqData.ok && seqData.groups) ? seqData.groups.length : 0;
    // 总分 = 各会话CT-30分数之和
    var totalScoreAll = 0;
    var totalTrialsAll = 0;
    var totalCorrectAll = 0;
    if (seqData.ok && seqData.groups) {
        seqData.groups.forEach(function(g) {
            g.items.forEach(function(it) {
                totalScoreAll += (it.score || 0);
                totalTrialsAll += (it.trial_count || 0);
                totalCorrectAll += (it.correct_count || 0);
            });
        });
    }
    var avgScore = sessionCount ? (totalScoreAll / sessionCount) : 0;
    var avgAcc = totalTrialsAll ? Math.round(totalCorrectAll / totalTrialsAll * 100) : 0;

    $("statSessions").textContent = sessionCount;
    $("statTrials").textContent = totalTrialsAll;
    $("statAvgScore").textContent = avgScore.toFixed(1);
    $("statAccuracy").textContent = avgAcc + "%";

    var list = $("sessionList");
    list.innerHTML = "";

    // 只显示顺序训练会话
    if (seqData.ok && seqData.groups && seqData.groups.length) {
        seqData.groups.forEach(function(g) {
            var dt = new Date(g.created_at).toLocaleString("zh-CN");
            var dur = Math.round(g.total_duration);
            var totalScore = 0;
            g.items.forEach(function(it) { totalScore += (it.score || 0); });
            var totalScoreRound = Math.round(totalScore * 100) / 100;
            var card = document.createElement("div");
            card.className = "session-card session-card-seq";
            card.onclick = function() { showSeqDetail(g); };
            card.oncontextmenu = function(e) {
                e.preventDefault();
                showSessionContextMenu(e, g);
            };
            card.innerHTML =
                '<div class="session-icon">🧠</div>' +
                '<div class="session-info">' +
                    '<div class="session-title">顺序训练 · 全5域</div>' +
                    '<div class="session-meta">' + dt + '  ·  ' + g.task_count + ' 项任务  ·  CT-30 ' + totalScoreRound + ' 分  ·  ' + dur + 's</div>' +
                '</div>' +
                '<div class="session-score">' + totalScoreRound + '<span class="session-score-unit">/30</span></div>' +
                '<div class="session-arrow">›</div>';
            list.appendChild(card);
        });
    } else {
        list.innerHTML = '<div class="empty-state"><div class="empty-emoji">\u{1F4CB}</div>暂无训练记录<br><span style="font-size:13px;">完成一次顺序训练后数据将显示在此处</span></div>';
    }
}

function taskEmoji(k) {
    var m = {orient:"🧭", memencode:"📖", trailblink:"🔗", semflow:"🏷️", nameblink:"💬"};
    return m[k] || "📋";
}

/* ===== 右键菜单 - 删除会话 ===== */
function showSessionContextMenu(e, group) {
    // 移除已有菜单
    var old = document.getElementById("sessionCtxMenu");
    if (old) old.remove();
    var menu = document.createElement("div");
    menu.id = "sessionCtxMenu";
    menu.className = "ctx-menu";
    menu.style.left = e.clientX + "px";
    menu.style.top = e.clientY + "px";
    menu.innerHTML =
        '<div class="ctx-menu-item ctx-menu-danger" data-action="delete">删除此会话</div>';
    document.body.appendChild(menu);
    // 点击删除
    menu.querySelector('[data-action="delete"]').onclick = function() {
        menu.remove();
        if (confirm("确定删除该训练会话？删除后不可恢复。")) {
            deleteSession(group.group_id);
        }
    };
    // 点击其他区域关闭
    setTimeout(function() {
        document.addEventListener("click", function closeMenu() {
            var m = document.getElementById("sessionCtxMenu");
            if (m) m.remove();
            document.removeEventListener("click", closeMenu);
        });
    }, 10);
}

async function deleteSession(groupId) {
    try {
        var res = await fetch(API + "/api/sequential_session/" + groupId, { method: "DELETE" });
        var data = await res.json();
        if (data.ok) {
            showToast("会话已删除", "success");
            _trajCache = null;
            loadRecords();
        } else {
            showToast("删除失败: " + (data.error || "未知错误"), "error");
        }
    } catch (e) {
        showToast("删除失败", "error");
    }
}

function showSeqDetail(g) {
    $("detailTitle").textContent = "顺序训练会话详情";
    var body = $("detailBody");
    var dt = new Date(g.created_at).toLocaleString("zh-CN");
    var totalScore = 0;
    g.items.forEach(function(it) { totalScore += (it.score || 0); });
    var totalScoreRound = Math.round(totalScore * 100) / 100;
    var totalTrials = 0, totalCorrect = 0;
    g.items.forEach(function(it) { totalTrials += (it.trial_count || 0); totalCorrect += (it.correct_count || 0); });
    var totalAcc = totalTrials ? Math.round(totalCorrect / totalTrials * 100) : 0;
    var html =
        '<div class="detail-meta">' + dt + '</div>' +
        '<div class="detail-summary-grid">' +
            '<div class="detail-summary-item"><div class="detail-summary-val">' + totalScoreRound + '</div><div class="detail-summary-label">CT-30 总分</div></div>' +
            '<div class="detail-summary-item"><div class="detail-summary-val">' + totalAcc + '%</div><div class="detail-summary-label">总正确率</div></div>' +
            '<div class="detail-summary-item"><div class="detail-summary-val">' + Math.round(g.total_duration || 0) + 's</div><div class="detail-summary-label">总用时</div></div>' +
        '</div>' +
        '<div class="detail-section-title">各任务得分 (每项满分6分)</div>' +
        '<div class="detail-task-list">';

    g.items.forEach(function(it, idx) {
        var acc = it.trial_count ? Math.round((it.correct_count / it.trial_count) * 100) : 0;
        var dur = Math.round(it.duration_sec || 0);
        html +=
            '<div class="detail-task-row">' +
                '<div class="detail-task-idx">' + (idx + 1) + '</div>' +
                '<div class="detail-task-info">' +
                    '<div class="detail-task-name">' + taskNameOf(it.task_key) + '</div>' +
                    '<div class="detail-task-meta">' + it.trial_count + ' 试次 · 正确率 ' + acc + '% · ' + dur + 's</div>' +
                '</div>' +
                '<div class="detail-task-score">' + it.score + '<span class="detail-task-score-unit">/6</span></div>' +
            '</div>';
    });

    html += '</div>';

    // 五维认知向量
    var cogLabels = ["定向力", "情景记忆", "执行功能", "语义记忆", "命名能力"];
    var cogMap = {orient: 0, memencode: 1, trailblink: 2, semflow: 3, nameblink: 4};
    var cogValues = [0, 0, 0, 0, 0];
    g.items.forEach(function(it) {
        var idx = cogMap[it.task_key];
        if (idx != null && it.trial_count) {
            cogValues[idx] = it.correct_count / it.trial_count;
        }
    });
    html += '<div class="detail-section-title">五维认知向量</div>';
    html += '<div class="detail-cog-bars">';
    cogLabels.forEach(function(label, i) {
        var val = (cogValues[i] * 100).toFixed(0);
        html +=
            '<div class="detail-cog-bar-row">' +
                '<div class="detail-cog-bar-label">' + label + '</div>' +
                '<div class="detail-cog-bar-track"><div class="detail-cog-bar-fill" style="width:' + val + '%;"></div></div>' +
                '<div class="detail-cog-bar-val">' + val + '%</div>' +
            '</div>';
    });
    html += '</div>';

    body.innerHTML = html;
    openDetail();
}

function openDetail() {
    $("detailPanel").classList.add("active");
    $("detailOverlay").classList.add("active");
}

function closeDetail() {
    $("detailPanel").classList.remove("active");
    $("detailOverlay").classList.remove("active");
}

function taskNameOf(k) {
    var m = {orient:"EEG-Orient 定向力",memencode:"EEG-MemEncode 情景记忆",trailblink:"EEG-TrailBlink 执行功能",semflow:"EEG-SemFlow 语义记忆",nameblink:"EEG-NameBlink 命名能力"};
    return m[k] || k;
}

/* ============== 轨迹追踪 ============== */
var COG_KEYS = ["orient", "memencode", "trailblink", "semflow", "nameblink"];
var COG_NAMES = ["定向力(D1)", "情景记忆(D2)", "执行功能(D3)", "语义记忆(D4)", "命名能力(D5)"];
var COG_COLORS = ["#E07A5F", "#3D85C6", "#6A994E", "#F2CC8F", "#81B29A"];
var TREND_LABELS = {"improving": "改善型", "stable": "维持型", "declining": "下滑型"};
var TREND_COLORS = {"improving": "#6A994E", "stable": "#9B8B7A", "declining": "#E07A5F"};
var _trajCache = null;  // 全局轨迹数据缓存

async function loadTrajectory() {
    var uid = state.currentUser;
    if (!uid) { $("trajSubtitle").textContent = "请先选择用户"; return; }

    try {
        var res = await fetch(API + "/api/trajectory/" + uid.user_id);
        var data = await res.json();

        // 无数据
        if (!data.ok || !data.trajectory) {
            $("trajSubtitle").textContent = "暂无顺序训练数据，完成顺序训练后即可查看轨迹";
            $("trajInsufficient").style.display = "none";
            $("trajSessions").textContent = "0";
            $("trajCT30").textContent = "--";
            $("trajTrend").textContent = "--";
            $("trajRiskLevel").textContent = "--";
            $("trajWarnings").style.display = "none";
            _trajCache = null;
            $("trajDownloadBtn").disabled = true;
            return;
        }

        var t = data.trajectory;
        var sufficient = data.sufficient;
        _trajCache = t;  // 缓存轨迹数据供逐试次展示
        _trajCache._sufficient = sufficient;
        $("trajDownloadBtn").disabled = false;
        $("trajSubtitle").textContent = "CSTM 跨会话认知轨迹建模 · " + uid.name;

        // 不足8次提示
        if (!sufficient) {
            $("trajInsufficient").style.display = "";
            $("trajCurrentCount").textContent = t.session_count;
        } else {
            $("trajInsufficient").style.display = "none";
        }

        // 概览
        $("trajSessions").textContent = t.session_count;
        $("trajCT30").textContent = t.total_scores[t.total_scores.length - 1].toFixed(1);
        $("trajTrend").textContent = t.overall_trend;
        $("trajTrend").style.color = t.overall_trend === "改善型" ? "#6A994E" : t.overall_trend === "下滑型" ? "#E07A5F" : "var(--text)";
        $("trajRiskLevel").textContent = t.risk_level;
        $("trajRiskLevel").style.color = t.risk_level === "高风险" ? "#E07A5F" : t.risk_level === "关注" ? "#D4A017" : "#6A994E";

        // 预警
        if (t.warnings && t.warnings.length > 0) {
            $("trajWarnings").style.display = "";
            $("trajWarningList").innerHTML = t.warnings.map(function(w) {
                var levelClass = w.level === "high" ? "traj-warn-high" : "traj-warn-medium";
                var levelLabel = w.level === "high" ? "高风险" : "关注";
                var levelBg = w.level === "high" ? "#FDE8E8" : "#FFF8E1";
                var dim = w.dimension ? '<div class="traj-warn-dim">' + w.dimension + '</div>' : '';
                var slope = (w.slope !== undefined) ? '<div class="traj-warn-slope">下滑斜率 β₁=' + w.slope.toFixed(3) + '</div>' : '';
                var ci = (w.ci) ? '<div class="traj-warn-ci">95%CI=[' + w.ci[0].toFixed(3) + ', ' + w.ci[1].toFixed(3) + ']</div>' : '';
                var typeLabel = {"cstm_decline":"维度下滑预警","cstm_overall_decline":"总分下滑预警","consecutive_decline":"连续下降预警","low_accuracy":"正确率异常","compliance":"依从性预警"}[w.type] || "预警";

                return '<div class="traj-warn-card ' + levelClass + '">' +
                    '<div class="traj-warn-header">' +
                        '<span class="traj-warn-badge" style="background:' + levelBg + ';">' + levelLabel + '</span>' +
                        '<span class="traj-warn-type">' + typeLabel + '</span>' +
                    '</div>' +
                    dim + slope + ci +
                    '<div class="traj-warn-msg">' + w.message + '</div>' +
                '</div>';
            }).join("");
        } else {
            $("trajWarnings").style.display = "none";
        }

        // D1-D5 认知向量折线图
        drawCogVectorChart(t, sufficient);

        // CT-30 总分折线图
        drawCT30Chart(t, sufficient);

        // 雷达图
        drawTrajRadarChart(t);

        // DMAP四象限
        drawDmapChart(t);

        // 轨迹分类
        drawClassification(t, sufficient);

        // 阶段性报告
        $("trajReport").innerHTML = "<pre class='traj-report-text'>" + t.report + "</pre>";

        // 会话明细表
        drawTrajTable(t);

    } catch (e) {
        console.error("轨迹加载失败", e);
    }
}

/* ---- D1-D5 认知向量折线图 (0-1 归一化) ---- */
function drawCogVectorChart(t, sufficient) {
    var canvas = $("trajLineChart");
    var ctx = canvas.getContext("2d");
    var dpr = window.devicePixelRatio || 1;
    var W = canvas.parentElement.clientWidth;
    var H = 320;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width = W + "px";
    canvas.style.height = H + "px";
    ctx.scale(dpr, dpr);

    var pad = {top: 30, right: 20, bottom: 50, left: 50};
    var cw = W - pad.left - pad.right;
    var ch = H - pad.top - pad.bottom;
    var n = t.session_count;
    if (n < 1) return;

    ctx.fillStyle = "#FAF6F0";
    ctx.fillRect(0, 0, W, H);

    // 网格 (0-1)
    ctx.strokeStyle = "#E8E0D8";
    ctx.lineWidth = 0.5;
    for (var i = 0; i <= 10; i++) {
        var y = pad.top + ch * (1 - i / 10);
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(pad.left + cw, y);
        ctx.stroke();
        ctx.fillStyle = "#9B8B7A";
        ctx.font = "11px sans-serif";
        ctx.textAlign = "right";
        ctx.fillText((i / 10).toFixed(1), pad.left - 8, y + 4);
    }

    // X轴标签
    ctx.textAlign = "center";
    ctx.fillStyle = "#9B8B7A";
    for (var i = 0; i < n; i++) {
        var x = pad.left + (n === 1 ? cw / 2 : cw * i / (n - 1));
        var label = t.session_labels[i] ? t.session_labels[i].substring(5, 10) : (i + 1);
        ctx.fillText(label, x, H - pad.bottom + 20);
    }

    // 各域折线 + 趋势线
    for (var d = 0; d < COG_KEYS.length; d++) {
        var vals = t.cog_vectors.map(function(v) { return v[d]; });
        // 实际数据线
        drawChartLine(ctx, vals, n, pad, cw, ch, COG_COLORS[d], 2, true, 1.0);
        // 拟合趋势线 (虚线)
        if (sufficient && t.regressions && t.regressions[COG_KEYS[d]]) {
            var reg = t.regressions[COG_KEYS[d]];
            var fitVals = [];
            for (var i = 0; i < n; i++) fitVals.push(reg.intercept + reg.slope * i);
            drawChartLine(ctx, fitVals, n, pad, cw, ch, COG_COLORS[d], 1.5, false, 0.4, true);
        }
    }

    // 图例
    ctx.font = "12px sans-serif";
    var legendX = pad.left + 10;
    var legendY = pad.top + 15;
    for (var d = 0; d < COG_KEYS.length; d++) {
        ctx.fillStyle = COG_COLORS[d];
        ctx.fillRect(legendX, legendY - 8, 16, 3);
        ctx.fillText(COG_NAMES[d], legendX + 22, legendY);
        legendX += 100;
    }
}

/* ---- CT-30 总分折线图 (0-30) ---- */
function drawCT30Chart(t, sufficient) {
    var canvas = $("trajTotalChart");
    var ctx = canvas.getContext("2d");
    var dpr = window.devicePixelRatio || 1;
    var W = canvas.parentElement.clientWidth;
    var H = 240;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width = W + "px";
    canvas.style.height = H + "px";
    ctx.scale(dpr, dpr);

    var pad = {top: 20, right: 20, bottom: 50, left: 50};
    var cw = W - pad.left - pad.right;
    var ch = H - pad.top - pad.bottom;
    var n = t.session_count;
    if (n < 1) return;

    ctx.fillStyle = "#FAF6F0";
    ctx.fillRect(0, 0, W, H);

    // 网格 (0-30)
    ctx.strokeStyle = "#E8E0D8";
    ctx.lineWidth = 0.5;
    for (var i = 0; i <= 6; i++) {
        var y = pad.top + ch * (1 - i * 5 / 30);
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(pad.left + cw, y);
        ctx.stroke();
        ctx.fillStyle = "#9B8B7A";
        ctx.font = "11px sans-serif";
        ctx.textAlign = "right";
        ctx.fillText((i * 5).toString(), pad.left - 8, y + 4);
    }

    // X轴
    ctx.textAlign = "center";
    ctx.fillStyle = "#9B8B7A";
    for (var i = 0; i < n; i++) {
        var x = pad.left + (n === 1 ? cw / 2 : cw * i / (n - 1));
        var label = t.session_labels[i] ? t.session_labels[i].substring(5, 10) : (i + 1);
        ctx.fillText(label, x, H - pad.bottom + 20);
    }

    // 总分折线
    drawChartLine(ctx, t.total_scores, n, pad, cw, ch, "#3D2C1E", 2.5, true, 1.0, false, 30);

    // 拟合趋势线
    if (sufficient && t.total_regression) {
        var reg = t.total_regression;
        var fitVals = [];
        for (var i = 0; i < n; i++) fitVals.push(reg.intercept + reg.slope * i);
        drawChartLine(ctx, fitVals, n, pad, cw, ch, "#3D2C1E", 1.5, false, 0.4, true, 30);
    }
}

function drawChartLine(ctx, vals, n, pad, cw, ch, color, width, showDots, alpha, dashed, maxVal) {
    if (!maxVal) maxVal = 1.0;
    ctx.save();
    ctx.globalAlpha = alpha || 1.0;
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    if (dashed) ctx.setLineDash([6, 4]);
    else ctx.setLineDash([]);
    ctx.beginPath();
    for (var i = 0; i < n; i++) {
        var x = pad.left + (n === 1 ? cw / 2 : cw * i / (n - 1));
        var y = pad.top + ch * (1 - vals[i] / maxVal);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    if (showDots) {
        ctx.fillStyle = color;
        for (var i = 0; i < n; i++) {
            var x = pad.left + (n === 1 ? cw / 2 : cw * i / (n - 1));
            var y = pad.top + ch * (1 - vals[i] / maxVal);
            ctx.beginPath();
            ctx.arc(x, y, 4, 0, Math.PI * 2);
            ctx.fill();
        }
    }
    ctx.restore();
}

/* ---- 认知雷达图 ---- */
function drawTrajRadarChart(t) {
    var canvas = $("trajRadarChart");
    var ctx = canvas.getContext("2d");
    var dpr = window.devicePixelRatio || 1;
    var size = Math.min(canvas.parentElement.clientWidth, 340);
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = size + "px";
    canvas.style.height = size + "px";
    ctx.scale(dpr, dpr);

    var cx = size / 2, cy = size / 2, R = size / 2 - 40, n = 5;

    ctx.fillStyle = "#FAF6F0";
    ctx.fillRect(0, 0, size, size);

    // 网格环
    for (var ring = 1; ring <= 5; ring++) {
        var r = R * ring / 5;
        ctx.strokeStyle = "#E8E0D8";
        ctx.lineWidth = 0.5;
        ctx.beginPath();
        for (var i = 0; i <= n; i++) {
            var angle = -Math.PI / 2 + (2 * Math.PI / n) * (i % n);
            var px = cx + r * Math.cos(angle), py = cy + r * Math.sin(angle);
            if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.stroke();
    }

    // 轴线 + 标签
    for (var i = 0; i < n; i++) {
        var angle = -Math.PI / 2 + (2 * Math.PI / n) * i;
        ctx.strokeStyle = "#D4C8BC";
        ctx.lineWidth = 0.5;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(cx + R * Math.cos(angle), cy + R * Math.sin(angle));
        ctx.stroke();

        var lx = cx + (R + 24) * Math.cos(angle);
        var ly = cy + (R + 24) * Math.sin(angle);
        ctx.fillStyle = "#5C4A3A";
        ctx.font = "12px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(COG_NAMES[i], lx, ly);
    }

    // 首次（虚线）vs 最近（实线）
    if (t.first_cog) drawRadarArea(ctx, cx, cy, R, t.first_cog, n, "rgba(61,44,30,0.1)", "rgba(61,44,30,0.4)", true);
    if (t.last_cog) drawRadarArea(ctx, cx, cy, R, t.last_cog, n, "rgba(106,153,78,0.15)", "rgba(106,153,78,0.8)", false);

    // 图例
    ctx.font = "11px sans-serif";
    ctx.fillStyle = "rgba(61,44,30,0.6)";
    ctx.fillRect(12, size - 28, 14, 3);
    ctx.fillText("首次会话", 32, size - 24);
    ctx.fillStyle = "rgba(106,153,78,0.8)";
    ctx.fillRect(100, size - 28, 14, 3);
    ctx.fillText("最近会话", 120, size - 24);
}

function drawRadarArea(ctx, cx, cy, R, values, n, fillColor, strokeColor, dashed) {
    ctx.beginPath();
    for (var i = 0; i <= n; i++) {
        var angle = -Math.PI / 2 + (2 * Math.PI / n) * (i % n);
        var v = Math.min(1, Math.max(0, values[i % n]));
        var px = cx + R * v * Math.cos(angle), py = cy + R * v * Math.sin(angle);
        if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.fillStyle = fillColor;
    ctx.fill();
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = dashed ? 1.5 : 2;
    if (dashed) ctx.setLineDash([4, 4]); else ctx.setLineDash([]);
    ctx.stroke();
    ctx.setLineDash([]);
}

/* ---- DMAP 四象限状态空间 ---- */
function drawDmapChart(t) {
    var canvas = $("trajDmapChart");
    var ctx = canvas.getContext("2d");
    var dpr = window.devicePixelRatio || 1;
    var size = Math.min(canvas.parentElement.clientWidth, 340);
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = size + "px";
    canvas.style.height = size + "px";
    ctx.scale(dpr, dpr);

    var pad = 50;
    var cw = size - pad * 2, ch = size - pad * 2;
    var cx = pad + cw / 2, cy = pad + ch / 2;

    ctx.fillStyle = "#FAF6F0";
    ctx.fillRect(0, 0, size, size);

    // 四象限背景
    // 左上：低注意-低疲劳（走神区）
    ctx.fillStyle = "rgba(242,204,143,0.15)";
    ctx.fillRect(pad, pad, cw / 2, ch / 2);
    // 右上：高注意-低疲劳（最优训练区）
    ctx.fillStyle = "rgba(106,153,78,0.12)";
    ctx.fillRect(cx, pad, cw / 2, ch / 2);
    // 左下：低注意-高疲劳（认知耗竭区）
    ctx.fillStyle = "rgba(224,122,95,0.12)";
    ctx.fillRect(pad, cy, cw / 2, ch / 2);
    // 右下：高注意-高疲劳（警惕疲劳累积区）
    ctx.fillStyle = "rgba(61,133,198,0.1)";
    ctx.fillRect(cx, cy, cw / 2, ch / 2);

    // 象限标签
    ctx.font = "11px sans-serif";
    ctx.textAlign = "center";
    ctx.fillStyle = "#9B8B7A";
    ctx.fillText("走神区", pad + cw / 4, pad + 18);
    ctx.fillStyle = "#6A994E";
    ctx.fillText("最优训练区", cx + cw / 4, pad + 18);
    ctx.fillStyle = "#E07A5F";
    ctx.fillText("认知耗竭区", pad + cw / 4, size - pad - 8);
    ctx.fillStyle = "#3D85C6";
    ctx.fillText("警惕疲劳区", cx + cw / 4, size - pad - 8);

    // 坐标轴
    ctx.strokeStyle = "#9B8B7A";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad, cy); ctx.lineTo(size - pad, cy);
    ctx.moveTo(cx, pad); ctx.lineTo(cx, size - pad);
    ctx.stroke();

    // 轴标签
    ctx.font = "12px sans-serif";
    ctx.fillStyle = "#5C4A3A";
    ctx.textAlign = "center";
    ctx.fillText("AI (注意力) →", cx, size - pad + 25);
    ctx.save();
    ctx.translate(pad - 25, cy);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText("CFI (疲劳) →", 0, 0);
    ctx.restore();

    // 数据点
    if (t.dmap_points) {
        for (var i = 0; i < t.dmap_points.length; i++) {
            var p = t.dmap_points[i];
            var x = pad + (p.ai / 100) * cw;
            var y = pad + (p.cfi / 100) * ch;
            // 连线
            if (i > 0) {
                var pp = t.dmap_points[i - 1];
                var px = pad + (pp.ai / 100) * cw;
                var py = pad + (pp.cfi / 100) * ch;
                ctx.strokeStyle = "rgba(61,44,30,0.2)";
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(px, py);
                ctx.lineTo(x, y);
                ctx.stroke();
            }
            // 点
            ctx.fillStyle = i === t.dmap_points.length - 1 ? "#3D2C1E" : "#B08968";
            ctx.beginPath();
            ctx.arc(x, y, i === t.dmap_points.length - 1 ? 5 : 3, 0, Math.PI * 2);
            ctx.fill();
            // 序号
            ctx.font = "10px sans-serif";
            ctx.fillStyle = "#5C4A3A";
            ctx.textAlign = "left";
            ctx.fillText(p.session, x + 6, y + 3);
        }
    }
}

/* ---- CSTM 轨迹分类 ---- */
function drawClassification(t, sufficient) {
    if (!sufficient) {
        $("trajClassification").innerHTML = '<p class="text-soft">需要至少8次会话数据才能生成轨迹分类</p>';
        return;
    }

    var html = '<div class="traj-class-grid">';
    for (var d = 0; d < COG_KEYS.length; d++) {
        var k = COG_KEYS[d];
        var trend = t.trends[k];
        var reg = t.regressions[k];
        var color = TREND_COLORS[trend];
        var label = TREND_LABELS[trend];

        html += '<div class="traj-class-item" style="border-left:4px solid ' + color + ';">';
        html += '<div class="traj-class-name">' + COG_NAMES[d] + '</div>';
        html += '<div class="traj-class-badge" style="background:' + color + ';">' + label + '</div>';
        if (reg) {
            html += '<div class="traj-class-detail">β₁=' + reg.slope.toFixed(3) + ' CI=[' + reg.ci_low.toFixed(3) + ',' + reg.ci_high.toFixed(3) + ']</div>';
        }
        html += '</div>';
    }
    html += '</div>';
    $("trajClassification").innerHTML = html;
}

/* ---- 会话明细表 ---- */
function drawTrajTable(t) {
    if (!t.raw_scores || t.raw_scores.length === 0) {
        $("trajTable").innerHTML = '<p class="text-soft">暂无数据</p>';
        return;
    }

    var html = '<table class="traj-table"><thead><tr>';
    html += '<th>会话</th><th>日期</th>';
    for (var d = 0; d < COG_NAMES.length; d++) {
        html += '<th>' + COG_NAMES[d] + '</th>';
    }
    html += '<th>CT-30</th><th>变化</th></tr></thead><tbody>';

    for (var i = 0; i < t.raw_scores.length; i++) {
        var s = t.raw_scores[i];
        var total = t.total_scores[i];
        var trend = "";
        if (i > 0) {
            var diff = total - t.total_scores[i - 1];
            if (diff > 0.5) trend = '<span style="color:#6A994E;">+' + diff.toFixed(1) + '</span>';
            else if (diff < -0.5) trend = '<span style="color:#E07A5F;">' + diff.toFixed(1) + '</span>';
            else trend = '<span style="color:#9B8B7A;">→</span>';
        }
        var date = t.session_labels[i] ? t.session_labels[i].substring(0, 10) : '-';
        html += '<tr>';
        html += '<td>' + (i + 1) + '</td>';
        html += '<td style="font-size:12px;">' + date + '</td>';
        for (var d = 0; d < COG_KEYS.length; d++) {
            var val = s[COG_KEYS[d]];
            var color = val >= 4 ? "#6A994E" : val >= 2 ? "#D4A017" : "#E07A5F";
            html += '<td style="color:' + color + '; font-weight:600;">' + val.toFixed(1) + '</td>';
        }
        html += '<td style="font-weight:700;">' + total.toFixed(1) + '</td>';
        html += '<td>' + trend + '</td>';
        html += '</tr>';
    }

    html += '</tbody></table>';
    $("trajTable").innerHTML = html;

    // 逐试次数据 - 填充会话选择下拉框
    if (t.trial_details && t.trial_details.length > 0) {
        var sel = $("trajTrialSession");
        sel.innerHTML = "";
        for (var i = 0; i < t.trial_details.length; i++) {
            var d = t.trial_details[i];
            var opt = document.createElement("option");
            opt.value = i;
            opt.textContent = "第" + d.session + "次 (" + (d.date ? d.date.substring(0, 10) : "-") + ")";
            sel.appendChild(opt);
        }
        // 默认选最近一次
        sel.value = t.trial_details.length - 1;
        drawTrialDetails();
    } else {
        $("trajTrialTable").innerHTML = '<p class="text-soft">暂无逐试次数据</p>';
    }
}

/* ---- 逐试次数据维度展示 (说明书8.1表7) ---- */
var TASK_KEY_NAMES = {orient:"定向力", memencode:"情景记忆", trailblink:"执行功能", semflow:"语义记忆", nameblink:"命名能力"};
var BLINK_TYPE_LABELS = {intentional:"有意眨眼", spontaneous:"自发眨眼", none:"无眨眼"};

function drawTrialDetails() {
    var sel = $("trajTrialSession");
    if (!sel || !sel.options.length) return;
    var idx = parseInt(sel.value);
    // 从全局缓存获取轨迹数据
    if (!_trajCache || !_trajCache.trial_details || idx >= _trajCache.trial_details.length) return;
    var detail = _trajCache.trial_details[idx];
    var trials = detail.trials || [];

    if (trials.length === 0) {
        $("trajTrialTable").innerHTML = '<p class="text-soft">该会话无逐试次记录</p>';
        return;
    }

    var html = '<table class="traj-table traj-trial-detail-table"><thead><tr>';
    html += '<th>#</th><th>任务</th><th>正确</th><th>眨眼类型</th><th>意图强度</th>';
    html += '<th>反应时间(ms)</th><th>Alpha(μV²)</th><th>Theta(μV²)</th><th>CFI</th><th>AI</th>';
    html += '</tr></thead><tbody>';

    for (var i = 0; i < trials.length; i++) {
        var tr = trials[i];
        var correctHtml = tr.is_correct ? '<span style="color:#6A994E;">✓</span>' : '<span style="color:#E07A5F;">✗</span>';
        var blinkLabel = BLINK_TYPE_LABELS[tr.blink_type] || tr.blink_type || "-";
        var intentLabel = tr.intent_level >= 2 ? "强" : (tr.intent_level === 1 ? "弱" : "-");
        var intentColor = tr.intent_level >= 2 ? "#E07A5F" : (tr.intent_level === 1 ? "#D4A017" : "#9B8B7A");
        var cfiColor = (tr.cfi_snapshot || 0) < 30 ? "#6A994E" : ((tr.cfi_snapshot || 0) < 60 ? "#D4A017" : "#E07A5F");

        html += '<tr>';
        html += '<td>' + (i + 1) + '</td>';
        html += '<td>' + (TASK_KEY_NAMES[tr.task_key] || tr.task_key || "-") + '</td>';
        html += '<td>' + correctHtml + '</td>';
        html += '<td>' + blinkLabel + '</td>';
        html += '<td style="color:' + intentColor + '; font-weight:600;">' + intentLabel + '</td>';
        html += '<td>' + (tr.reaction_time_ms || "-") + '</td>';
        html += '<td>' + (tr.alpha_power ? tr.alpha_power.toFixed(1) : "-") + '</td>';
        html += '<td>' + (tr.theta_power ? tr.theta_power.toFixed(1) : "-") + '</td>';
        html += '<td style="color:' + cfiColor + '; font-weight:600;">' + (tr.cfi_snapshot ? tr.cfi_snapshot.toFixed(1) : "-") + '</td>';
        html += '<td>' + (tr.ai_snapshot ? tr.ai_snapshot.toFixed(1) : "-") + '</td>';
        html += '</tr>';
    }

    html += '</tbody></table>';
    $("trajTrialTable").innerHTML = html;
}

/* ============== 轨迹报告下载 ============== */
function _escHtml(s) {
    return String(s == null ? "" : s)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/* 以高倍率重绘图表并捕获 PNG dataURL（保证导出图片清晰度） */
function _captureTrajCharts(t, sufficient) {
    var charts = [
        {fn: function() { drawCogVectorChart(t, sufficient); }, id: "trajLineChart"},
        {fn: function() { drawCT30Chart(t, sufficient); }, id: "trajTotalChart"},
        {fn: function() { drawTrajRadarChart(t); }, id: "trajRadarChart"},
        {fn: function() { drawDmapChart(t); }, id: "trajDmapChart"}
    ];
    var hiDpr = Math.max(3, window.devicePixelRatio || 1);
    var origDpr = window.devicePixelRatio;
    var result = {};
    var overridden = false;
    try {
        try {
            Object.defineProperty(window, "devicePixelRatio", {value: hiDpr, configurable: true});
            overridden = true;
        } catch (e) { /* 浏览器不允许覆写时按原生分辨率导出 */ }
        for (var i = 0; i < charts.length; i++) {
            charts[i].fn();
            var cv = $(charts[i].id);
            result[charts[i].id] = cv.toDataURL("image/png");
        }
    } finally {
        if (overridden) {
            try { Object.defineProperty(window, "devicePixelRatio", {value: origDpr, configurable: true}); } catch (e) {}
        }
        for (var j = 0; j < charts.length; j++) charts[j].fn();  // 恢复屏幕分辨率重绘
    }
    return result;
}

function _buildReportTable(rows, headers, aligns) {
    var html = "<table><thead><tr>";
    for (var i = 0; i < headers.length; i++) html += "<th>" + headers[i] + "</th>";
    html += "</tr></thead><tbody>";
    for (var r = 0; r < rows.length; r++) {
        html += "<tr>";
        for (var c = 0; c < rows[r].length; c++) {
            html += "<td" + (aligns && aligns[c] ? ' style="text-align:' + aligns[c] + ';"' : "") + ">" + rows[r][c] + "</td>";
        }
        html += "</tr>";
    }
    return html + "</tbody></table>";
}

/* ---- 单通道EEG统计分析 ---- */
function _mean(vals) {
    var s = 0, c = 0;
    for (var i = 0; i < vals.length; i++) {
        var v = vals[i];
        if (v != null && isFinite(v)) { s += v; c++; }
    }
    return c ? s / c : null;
}

function _pearson(xs, ys) {
    var n = Math.min(xs.length, ys.length);
    if (n < 3) return null;
    var mx = 0, my = 0, i;
    for (i = 0; i < n; i++) { mx += xs[i]; my += ys[i]; }
    mx /= n; my /= n;
    var sxy = 0, sxx = 0, syy = 0;
    for (i = 0; i < n; i++) {
        var dx = xs[i] - mx, dy = ys[i] - my;
        sxy += dx * dy; sxx += dx * dx; syy += dy * dy;
    }
    if (!sxx || !syy) return null;
    return sxy / Math.sqrt(sxx * syy);
}

function _corrDesc(r) {
    if (r == null) return "样本不足";
    var a = Math.abs(r);
    var mag = a < 0.1 ? "几乎无" : a < 0.3 ? "弱" : a < 0.5 ? "中等" : "强";
    return mag + (r >= 0 ? "正相关" : "负相关");
}

/* 汇总全部逐试次 EEG 数据：会话级 / 任务域级 / 总体 / 相关性 */
function _analyzeEEG(t) {
    var details = t.trial_details || [];
    var all = [];
    details.forEach(function(det) {
        (det.trials || []).forEach(function(tr) {
            tr._session = det.session;
            tr._date = det.date;
            all.push(tr);
        });
    });
    var hasEEG = all.filter(function(tr) {
        return tr.alpha_power != null || tr.theta_power != null ||
               tr.cfi_snapshot != null || tr.ai_snapshot != null;
    });
    if (!hasEEG.length) return null;

    // 会话级 EEG 指标
    var sessions = details.map(function(det) {
        var trs = det.trials || [];
        var blinks = trs.filter(function(tr) { return tr.blink_type && tr.blink_type !== "none"; });
        var intentional = trs.filter(function(tr) { return tr.blink_type === "intentional"; });
        var alpha = _mean(trs.map(function(tr) { return tr.alpha_power; }));
        var theta = _mean(trs.map(function(tr) { return tr.theta_power; }));
        return {
            session: det.session,
            date: det.date || "",
            n: trs.length,
            alpha: alpha,
            theta: theta,
            tar: (alpha != null && theta != null && alpha > 0.01) ? theta / alpha : null,
            ai: _mean(trs.map(function(tr) { return tr.ai_snapshot; })),
            cfi: _mean(trs.map(function(tr) { return tr.cfi_snapshot; })),
            blinkTotal: blinks.length,
            intentional: intentional.length,
            intentRate: blinks.length ? intentional.length / blinks.length : null,
            protL1: trs.filter(function(tr) { return tr.cfi_snapshot >= 40; }).length,
            protL2: trs.filter(function(tr) { return tr.cfi_snapshot >= 60; }).length,
            protL3: trs.filter(function(tr) { return tr.cfi_snapshot >= 80; }).length
        };
    }).filter(function(s) { return s.n > 0; });

    // 任务域级 EEG 指标
    var tasks = {};
    all.forEach(function(tr) {
        var k = tr.task_key || "unknown";
        if (!tasks[k]) tasks[k] = [];
        tasks[k].push(tr);
    });
    var taskStats = [];
    COG_KEYS.forEach(function(k, idx) {
        var trs = tasks[k] || [];
        if (!trs.length) return;
        var alpha = _mean(trs.map(function(tr) { return tr.alpha_power; }));
        var theta = _mean(trs.map(function(tr) { return tr.theta_power; }));
        var correct = trs.filter(function(tr) { return tr.is_correct; }).length;
        var blinks = trs.filter(function(tr) { return tr.blink_type && tr.blink_type !== "none"; });
        var intentional = trs.filter(function(tr) { return tr.blink_type === "intentional"; });
        taskStats.push({
            key: k, name: COG_NAMES[idx], n: trs.length,
            acc: correct / trs.length,
            alpha: alpha, theta: theta,
            tar: (alpha != null && theta != null && alpha > 0.01) ? theta / alpha : null,
            ai: _mean(trs.map(function(tr) { return tr.ai_snapshot; })),
            cfi: _mean(trs.map(function(tr) { return tr.cfi_snapshot; })),
            rt: _mean(trs.map(function(tr) { return tr.reaction_time_ms; })),
            intentRate: blinks.length ? intentional.length / blinks.length : null
        });
    });

    // 总体眨眼分布
    var blinkDist = {intentional: 0, spontaneous: 0, none: 0};
    all.forEach(function(tr) {
        var b = tr.blink_type || "none";
        blinkDist[b] = (blinkDist[b] || 0) + 1;
    });

    // 三级保护触发（全期累计）
    var prot = {
        l1: all.filter(function(tr) { return tr.cfi_snapshot >= 40; }).length,
        l2: all.filter(function(tr) { return tr.cfi_snapshot >= 60; }).length,
        l3: all.filter(function(tr) { return tr.cfi_snapshot >= 80; }).length
    };

    // EEG-行为相关性（试次级）
    var pairs = {tarAcc: [[], []], aiRt: [[], []], aiAcc: [[], []], cfiAcc: [[], []]};
    all.forEach(function(tr) {
        var acc = tr.is_correct ? 1 : 0;
        if (tr.alpha_power != null && tr.theta_power != null && tr.alpha_power > 0.01) {
            pairs.tarAcc[0].push(tr.theta_power / tr.alpha_power);
            pairs.tarAcc[1].push(acc);
        }
        if (tr.ai_snapshot != null) {
            pairs.aiAcc[0].push(tr.ai_snapshot);
            pairs.aiAcc[1].push(acc);
            if (tr.reaction_time_ms != null && tr.reaction_time_ms > 0) {
                pairs.aiRt[0].push(tr.ai_snapshot);
                pairs.aiRt[1].push(tr.reaction_time_ms);
            }
        }
        if (tr.cfi_snapshot != null) {
            pairs.cfiAcc[0].push(tr.cfi_snapshot);
            pairs.cfiAcc[1].push(acc);
        }
    });
    var corr = {
        tarAcc: _pearson(pairs.tarAcc[0], pairs.tarAcc[1]),
        aiRt: _pearson(pairs.aiRt[0], pairs.aiRt[1]),
        aiAcc: _pearson(pairs.aiAcc[0], pairs.aiAcc[1]),
        cfiAcc: _pearson(pairs.cfiAcc[0], pairs.cfiAcc[1])
    };

    // 总体均值
    var overall = {
        n: all.length,
        alpha: _mean(all.map(function(tr) { return tr.alpha_power; })),
        theta: _mean(all.map(function(tr) { return tr.theta_power; })),
        ai: _mean(all.map(function(tr) { return tr.ai_snapshot; })),
        cfi: _mean(all.map(function(tr) { return tr.cfi_snapshot; })),
        rt: _mean(all.map(function(tr) { return tr.reaction_time_ms; }))
    };
    overall.tar = (overall.alpha != null && overall.theta != null && overall.alpha > 0.01)
        ? overall.theta / overall.alpha : null;

    return {sessions: sessions, taskStats: taskStats, blinkDist: blinkDist,
            prot: prot, corr: corr, overall: overall};
}

/* ---- 频段节律与PSD分析（AD电生理标志物） ---- */
var PSD_BANDS = [
    {key: "delta_power", name: "Delta (δ)", range: "1-4 Hz",  color: "#8E6BB5", role: "深睡/病理慢波"},
    {key: "theta_power", name: "Theta (θ)", range: "4-8 Hz",  color: "#E07A5F", role: "工作记忆/困倦负荷"},
    {key: "alpha_power", name: "Alpha (α)", range: "8-13 Hz", color: "#3D85C6", role: "皮层警觉/放松注意"},
    {key: "beta_power",  name: "Beta (β)",  range: "13-30 Hz",color: "#6A994E", role: "主动认知加工"},
    {key: "gamma_power", name: "Gamma (γ)", range: "30-50 Hz",color: "#D4A017", role: "高级信息整合"}
];

function _analyzePSD(t) {
    var details = t.trial_details || [];
    var all = [];
    details.forEach(function(det) {
        (det.trials || []).forEach(function(tr) {
            tr._session = det.session;
            tr._date = det.date;
            all.push(tr);
        });
    });
    var withEEG = all.filter(function(tr) {
        return (tr.alpha_power > 0) || (tr.theta_power > 0);
    });
    if (!withEEG.length) return null;

    var bandMeans = function(trs) {
        var m = {};
        PSD_BANDS.forEach(function(b) { m[b.key] = _mean(trs.map(function(tr) { return tr[b.key]; })); });
        return m;
    };
    var relOf = function(m) {
        var total = 0;
        PSD_BANDS.forEach(function(b) { if (m[b.key] != null && m[b.key] > 0) total += m[b.key]; });
        var rel = {};
        PSD_BANDS.forEach(function(b) { rel[b.key] = (m[b.key] != null && total > 0) ? m[b.key] / total : null; });
        rel._total = total;
        return rel;
    };
    var markersOf = function(m) {
        var a = m.alpha_power || 0, th = m.theta_power || 0, d = m.delta_power || 0, be = m.beta_power || 0;
        return {
            tar: (a > 0.01) ? th / a : null,                                  // θ/α EEG慢化核心标志
            si: (a + be > 0.01) ? (d + th) / (a + be) : null,                 // 慢化指数 (δ+θ)/(α+β)
            dai: (a > 0.01) ? d / a : null                                    // δ/α 指数
        };
    };

    var overall = bandMeans(withEEG);
    var rel = relOf(overall);
    var markers = markersOf(overall);

    // 逐会话频段轨迹
    var sessions = [];
    details.forEach(function(det) {
        var trs = (det.trials || []).filter(function(tr) {
            return (tr.alpha_power > 0) || (tr.theta_power > 0);
        });
        if (!trs.length) return;
        var m = bandMeans(trs);
        var r = relOf(m);
        var mk = markersOf(m);
        sessions.push({session: det.session, date: det.date || "", n: trs.length,
                       means: m, rel: r, tar: mk.tar, si: mk.si});
    });

    // 逐任务域频段特征
    var byTask = {};
    withEEG.forEach(function(tr) {
        var k = tr.task_key || "unknown";
        if (!byTask[k]) byTask[k] = [];
        byTask[k].push(tr);
    });
    var taskPSD = [];
    COG_KEYS.forEach(function(k, idx) {
        var trs = byTask[k] || [];
        if (!trs.length) return;
        var m = bandMeans(trs);
        var r = relOf(m);
        var mk = markersOf(m);
        taskPSD.push({key: k, name: COG_NAMES[idx], n: trs.length, means: m, rel: r,
                      tar: mk.tar, si: mk.si, alpha: m.alpha_power, theta: m.theta_power});
    });

    return {overall: overall, rel: rel, markers: markers, sessions: sessions,
            taskPSD: taskPSD, n: withEEG.length, totalTrials: all.length};
}

/* PSD 功率谱条形图：绝对功率 + 相对功率标注（离屏3x高清渲染） */
function _renderPSDChart(psd) {
    var W = 820, H = 320, dpr = 3;
    var cv = document.createElement("canvas");
    cv.width = W * dpr; cv.height = H * dpr;
    var ctx = cv.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.fillStyle = "#FAF6F0";
    ctx.fillRect(0, 0, W, H);

    var pad = {top: 42, right: 20, bottom: 58, left: 54};
    var cw = W - pad.left - pad.right, ch = H - pad.top - pad.bottom;
    var vals = PSD_BANDS.map(function(b) { return psd.overall[b.key] || 0; });
    var maxV = Math.max.apply(null, vals.concat([1]));
    var yMax = Math.ceil(maxV / 10) * 10;
    var nB = PSD_BANDS.length;
    var slot = cw / nB, barW = slot * 0.52;

    // Y轴网格
    ctx.font = "11px sans-serif";
    for (var i = 0; i <= 5; i++) {
        var v = yMax * i / 5;
        var y = pad.top + ch * (1 - i / 5);
        ctx.strokeStyle = "#E8E0D8";
        ctx.lineWidth = 0.5;
        ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + cw, y); ctx.stroke();
        ctx.fillStyle = "#9B8B7A";
        ctx.textAlign = "right";
        ctx.fillText(v.toFixed(0), pad.left - 8, y + 4);
    }
    ctx.save();
    ctx.translate(14, pad.top + ch / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillStyle = "#8A7A6A";
    ctx.font = "11px sans-serif";
    ctx.fillText("平均功率 (μV²)", 0, 0);
    ctx.restore();

    // 条形
    PSD_BANDS.forEach(function(b, idx) {
        var val = psd.overall[b.key] || 0;
        var x = pad.left + slot * idx + (slot - barW) / 2;
        var h = ch * val / yMax;
        var y = pad.top + ch - h;
        ctx.fillStyle = b.color;
        ctx.beginPath();
        if (ctx.roundRect) { ctx.roundRect(x, y, barW, h, [4, 4, 0, 0]); ctx.fill(); }
        else ctx.fillRect(x, y, barW, h);
        // 数值 + 相对功率
        ctx.fillStyle = "#3D2C1E";
        ctx.textAlign = "center";
        ctx.font = "bold 11px sans-serif";
        ctx.fillText(val.toFixed(1), x + barW / 2, y - 16);
        var rp = psd.rel[b.key];
        ctx.fillStyle = "#8A7A6A";
        ctx.font = "10px sans-serif";
        ctx.fillText(rp != null ? (rp * 100).toFixed(1) + "%" : "—", x + barW / 2, y - 4);
        // X轴标签
        ctx.fillStyle = b.color;
        ctx.font = "bold 12px sans-serif";
        ctx.fillText(b.name, x + barW / 2, H - pad.bottom + 18);
        ctx.fillStyle = "#9B8B7A";
        ctx.font = "10px sans-serif";
        ctx.fillText(b.range, x + barW / 2, H - pad.bottom + 32);
        ctx.fillText(b.role, x + barW / 2, H - pad.bottom + 45);
    });

    ctx.fillStyle = "#6B3A1F";
    ctx.font = "bold 13px sans-serif";
    ctx.textAlign = "left";
    ctx.fillText("全期平均功率谱密度（PSD）— Fp1 单通道", pad.left, 22);
    return cv.toDataURL("image/png");
}

/* AD标志物跨会话趋势图：TAR(θ/α) 与 慢化指数SI（离屏3x渲染） */
function _renderPSDTrendChart(sess) {
    var W = 820, H = 300, dpr = 3;
    var cv = document.createElement("canvas");
    cv.width = W * dpr; cv.height = H * dpr;
    var ctx = cv.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.fillStyle = "#FAF6F0";
    ctx.fillRect(0, 0, W, H);

    var pad = {top: 40, right: 20, bottom: 42, left: 50};
    var cw = W - pad.left - pad.right, ch = H - pad.top - pad.bottom;
    var n = sess.length;
    var allVals = [];
    sess.forEach(function(s) {
        if (s.tar != null) allVals.push(s.tar);
        if (s.si != null) allVals.push(s.si);
    });
    var vMax = Math.max.apply(null, allVals.concat([1]));
    vMax = Math.ceil(vMax * 10) / 10;
    var xAt = function(i) { return pad.left + (n === 1 ? cw / 2 : cw * i / (n - 1)); };
    var yAt = function(v) { return pad.top + ch * (1 - v / vMax); };

    // 网格
    ctx.font = "11px sans-serif";
    for (var i = 0; i <= 4; i++) {
        var v = vMax * i / 4;
        var y = yAt(v);
        ctx.strokeStyle = "#E8E0D8";
        ctx.lineWidth = 0.5;
        ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + cw, y); ctx.stroke();
        ctx.fillStyle = "#9B8B7A";
        ctx.textAlign = "right";
        ctx.fillText(v.toFixed(1), pad.left - 8, y + 4);
    }
    // X标签
    ctx.textAlign = "center";
    for (var s = 0; s < n; s++) {
        ctx.fillStyle = "#9B8B7A";
        ctx.fillText("S" + sess[s].session, xAt(s), H - pad.bottom + 18);
    }

    var drawLine = function(get, color, label) {
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.2;
        ctx.beginPath();
        var started = false;
        for (var i = 0; i < n; i++) {
            var v = get(sess[i]);
            if (v == null) continue;
            var x = xAt(i), y = yAt(v);
            if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.fillStyle = color;
        for (var j = 0; j < n; j++) {
            var vv = get(sess[j]);
            if (vv == null) continue;
            ctx.beginPath();
            ctx.arc(xAt(j), yAt(vv), 3.5, 0, Math.PI * 2);
            ctx.fill();
        }
    };
    drawLine(function(s) { return s.tar; }, "#C0392B");
    drawLine(function(s) { return s.si; }, "#8E6BB5");

    // 图例
    ctx.font = "12px sans-serif";
    ctx.textAlign = "left";
    ctx.fillStyle = "#C0392B";
    ctx.fillRect(pad.left, 14, 18, 3);
    ctx.fillText("TAR (θ/α) — EEG慢化核心标志", pad.left + 24, 20);
    ctx.fillStyle = "#8E6BB5";
    ctx.fillRect(pad.left + 250, 14, 18, 3);
    ctx.fillText("SI (δ+θ)/(α+β) — 慢化指数", pad.left + 274, 20);
    return cv.toDataURL("image/png");
}

/* 相对功率雷达/分布图（各任务域θ/α热区） */
function _renderTaskPSDChart(taskPSD) {
    var W = 820, H = 300, dpr = 3;
    var cv = document.createElement("canvas");
    cv.width = W * dpr; cv.height = H * dpr;
    var ctx = cv.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.fillStyle = "#FAF6F0";
    ctx.fillRect(0, 0, W, H);

    var pad = {top: 44, right: 20, bottom: 46, left: 50};
    var cw = W - pad.left - pad.right, ch = H - pad.top - pad.bottom;
    var nT = taskPSD.length;
    var nB = PSD_BANDS.length;
    var groupW = cw / Math.max(nT, 1);
    var barW = groupW * 0.78 / nB;

    // 相对功率 Y 轴 (0-100%)
    ctx.font = "11px sans-serif";
    for (var i = 0; i <= 5; i++) {
        var v = i * 20;
        var y = pad.top + ch * (1 - v / 100);
        ctx.strokeStyle = "#E8E0D8";
        ctx.lineWidth = 0.5;
        ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + cw, y); ctx.stroke();
        ctx.fillStyle = "#9B8B7A";
        ctx.textAlign = "right";
        ctx.fillText(v + "%", pad.left - 8, y + 4);
    }

    taskPSD.forEach(function(tp, ti) {
        var gx = pad.left + groupW * ti;
        PSD_BANDS.forEach(function(b, bi) {
            var rp = tp.rel[b.key];
            if (rp == null) return;
            var pctV = Math.min(100, rp * 100);
            var x = gx + groupW * 0.11 + barW * bi;
            var h = ch * pctV / 100;
            ctx.fillStyle = b.color;
            ctx.globalAlpha = 0.88;
            ctx.beginPath();
            if (ctx.roundRect) { ctx.roundRect(x, pad.top + ch - h, barW * 0.86, h, [3, 3, 0, 0]); ctx.fill(); }
            else ctx.fillRect(x, pad.top + ch - h, barW * 0.86, h);
            ctx.globalAlpha = 1;
        });
        ctx.fillStyle = "#3D2C1E";
        ctx.font = "bold 12px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(tp.name, gx + groupW / 2, H - pad.bottom + 20);
        ctx.fillStyle = "#8A7A6A";
        ctx.font = "10px sans-serif";
        ctx.fillText("θ/α=" + (tp.tar != null ? tp.tar.toFixed(2) : "—"), gx + groupW / 2, H - pad.bottom + 34);
    });

    // 频段图例
    ctx.font = "11px sans-serif";
    ctx.textAlign = "left";
    var lx = pad.left;
    PSD_BANDS.forEach(function(b) {
        ctx.fillStyle = b.color;
        ctx.fillRect(lx, 16, 12, 12);
        ctx.fillStyle = "#3D2C1E";
        ctx.fillText(b.name, lx + 16, 26);
        lx += 16 + ctx.measureText(b.name).width + 22;
    });
    return cv.toDataURL("image/png");
}

/* 生成 PSD 章节 HTML */
function _buildPSDSection(psd) {
    var fmt = function(v, d) { return v == null ? "—" : v.toFixed(d === undefined ? 2 : d); };
    var pct = function(v) { return v == null ? "—" : (v * 100).toFixed(1) + "%"; };
    var m = psd.markers;

    // AD 标志物 KPI
    var kpi = '<div class="summary" style="grid-template-columns:repeat(5,1fr); margin-bottom:14px;">' +
        '<div class="sum-card"><div class="num">' + fmt(m.tar) + '</div><div class="lab">TAR (θ/α)<br>EEG慢化核心标志</div></div>' +
        '<div class="sum-card"><div class="num">' + fmt(m.si) + '</div><div class="lab">SI (δ+θ)/(α+β)<br>慢化指数</div></div>' +
        '<div class="sum-card"><div class="num">' + fmt(m.dai) + '</div><div class="lab">DAI (δ/α)<br>深慢波指数</div></div>' +
        '<div class="sum-card"><div class="num" style="color:#3D85C6;">' + pct(psd.rel.alpha_power) + '</div><div class="lab">Alpha 相对功率</div></div>' +
        '<div class="sum-card"><div class="num" style="color:#E07A5F;">' + pct(psd.rel.theta_power) + '</div><div class="lab">Theta 相对功率</div></div>' +
        '</div>';

    // 频段功率谱表
    var bandRows = PSD_BANDS.map(function(b) {
        var abs = psd.overall[b.key];
        var rp = psd.rel[b.key];
        return [_escHtml(b.name), b.range, b.role,
                abs != null ? abs.toFixed(1) : "—",
                pct(rp)];
    });
    var bandTable = '<h3>5.1 五频段功率谱密度（PSD）</h3>' +
        _buildReportTable(bandRows, ["频段", "频率范围", "认知功能关联", "全期平均功率(μV²)", "相对功率占比"],
            [null, "center", null, "right", "right"]) +
        '<p class="note">基于 TGAM 单通道 Fp1（512Hz 采样）8频段原始功率合并计算：Delta(1-4Hz)、Theta(4-8Hz)、Alpha(8-13Hz, 含低/高α)、Beta(13-30Hz, 含低/高β)、Gamma(30-50Hz)。相对功率 = 该频段功率 / 五频段总功率。</p>' +
        '<img class="chart-img" src="' + _renderPSDChart(psd) + '" alt="PSD功率谱">';

    // 任务域频段分布
    var taskRows = psd.taskPSD.map(function(tp) {
        return [_escHtml(tp.name), tp.n,
                pct(tp.rel.delta_power), pct(tp.rel.theta_power), pct(tp.rel.alpha_power),
                pct(tp.rel.beta_power), pct(tp.rel.gamma_power),
                fmt(tp.tar), fmt(tp.si)];
    });
    var taskTable = '<h3>5.2 各认知任务域频段相对功率</h3>' +
        _buildReportTable(taskRows,
            ["认知域", "试次", "δ RP", "θ RP", "α RP", "β RP", "γ RP", "θ/α", "SI"],
            [null, "right", "right", "right", "right", "right", "right", "right", "right"]) +
        '<img class="chart-img" src="' + _renderTaskPSDChart(psd.taskPSD) + '" alt="任务域频段分布">' +
        '<p class="note">RP=相对功率。不同认知任务诱发的频段能量分布差异，反映各认知域的神经振荡需求特征。</p>';

    // 跨会话节律趋势
    var sessRows = psd.sessions.map(function(s) {
        return ["S" + s.session, _escHtml((s.date || "").substring(0, 10)), s.n,
                s.means.theta_power != null ? s.means.theta_power.toFixed(1) : "—",
                s.means.alpha_power != null ? s.means.alpha_power.toFixed(1) : "—",
                pct(s.rel.delta_power), pct(s.rel.theta_power), pct(s.rel.alpha_power),
                pct(s.rel.beta_power), fmt(s.tar), fmt(s.si)];
    });
    var sessTable = '<h3>5.3 节律指标跨会话趋势</h3>' +
        _buildReportTable(sessRows,
            ["会话", "日期", "试次", "θ功率", "α功率", "δ RP", "θ RP", "α RP", "β RP", "TAR θ/α", "SI"],
            [null, null, "right", "right", "right", "right", "right", "right", "right", "right", "right"]) +
        '<img class="chart-img" src="' + _renderPSDTrendChart(psd.sessions) + '" alt="TAR/SI趋势">';

    // 临床解读（数据驱动）
    var bullets = [];
    var S = psd.sessions;
    var trendInfo = {earlyTAR: null, lateTAR: null, dTAR: null, dir: "flat"};
    if (S.length >= 2) {
        var k = Math.max(1, Math.floor(S.length / 3));
        trendInfo.earlyTAR = _mean(S.slice(0, k).map(function(x) { return x.tar; }));
        trendInfo.lateTAR = _mean(S.slice(-k).map(function(x) { return x.tar; }));
        if (trendInfo.earlyTAR != null && trendInfo.lateTAR != null) {
            trendInfo.dTAR = trendInfo.lateTAR - trendInfo.earlyTAR;
            trendInfo.dir = trendInfo.dTAR > 0.05 ? "up" : trendInfo.dTAR < -0.05 ? "down" : "flat";
            bullets.push("<b>θ/α 比值（TAR）轨迹</b>：前期均值 " + fmt(trendInfo.earlyTAR) + " → 近期 " + fmt(trendInfo.lateTAR) +
                "（" + (trendInfo.dir === "up" ? "上升" : trendInfo.dir === "down" ? "下降" : "平稳") + "）。" +
                (trendInfo.dir === "up"
                    ? "TAR 进行性升高是 AD/MCI 患者 EEG 慢化的核心电生理标志（theta 活动增强伴 alpha 功率降低），建议结合 CT-30 轨迹进行临床复核。"
                    : trendInfo.dir === "down"
                        ? "TAR 下行提示 EEG 慢化趋势缓解、alpha 节律恢复，与认知训练干预的正向效应一致。"
                        : "TAR 保持稳定，未观察到进行性 EEG 慢化。"));
        }
    }
    var aRP = psd.rel.alpha_power, tRP = psd.rel.theta_power;
    if (aRP != null) {
        bullets.push("<b>Alpha 相对功率</b>：" + pct(aRP) +
            "。AD 早期患者典型表现为 alpha 功率降低（与情景记忆及注意力下降显著相关，Goodman 2020）；" +
            (aRP < 0.2 ? "当前 alpha 占比偏低，提示皮层警觉资源不足，建议关注训练时段的清醒状态。" :
             aRP < 0.35 ? "处于中等水平，建议纵向追踪其变化趋势。" :
             "占比尚可，皮层 α 节律维持相对完整。"));
    }
    if (tRP != null) {
        bullets.push("<b>Theta 相对功率</b>：" + pct(tRP) +
            "。theta 调制异常反映工作记忆效率减退；训练负荷下 theta 短时升高属生理性反应，" +
            "持续走高则需警惕病理性慢波化。");
    }
    if (psd.rel.beta_power != null) {
        bullets.push("<b>Beta/Gamma 快波活动</b>：β RP " + pct(psd.rel.beta_power) + "、γ RP " + pct(psd.rel.gamma_power) +
            "。快波成分反映主动认知加工与高级信息整合能力，AD 患者常见 β 活动减弱。");
    }
    if (psd.taskPSD.length >= 2) {
        var maxTar = psd.taskPSD.reduce(function(a, b) { return (b.tar || 0) > (a.tar || 0) ? b : a; });
        var minTar = psd.taskPSD.reduce(function(a, b) { return (b.tar || 0) < (a.tar || 0) ? b : a; });
        if (maxTar.tar != null && minTar.tar != null && maxTar.key !== minTar.key) {
            bullets.push("<b>任务诱发节律差异</b>：θ/α 最高的任务域为" + _escHtml(maxTar.name) + "（" + fmt(maxTar.tar) +
                "），最低为" + _escHtml(minTar.name) + "（" + fmt(minTar.tar) +
                "），提示前者诱发的慢波负荷更高，可作为个性化难度调整的 EEG 依据。");
        }
    }
    var interpret = '<h3>5.4 AD 电生理标志物解读</h3><ul class="eeg-bullets">' +
        bullets.map(function(b) { return "<li>" + b + "</li>"; }).join("") + "</ul>" +
        '<p class="note">注：TAR=θ/α（Theta-Alpha Ratio）；SI=慢化指数(δ+θ)/(α+β)；DAI=δ/α。' +
        '指标基于逐试次 Fp1 单通道 EEG 快照的全期汇总（共 ' + psd.n + '/' + psd.totalTrials + ' 试次含有效频段数据），仅供纵向对照参考，不作为临床诊断依据。</p>';

    // 综合结论（面向医生与照护者）
    var riskScore = 0;
    var riskReasons = [];
    var m2 = psd.markers;
    if (trendInfo.dir === "up") {
        riskScore += 2;
        riskReasons.push("θ/α 比值呈进行性上升趋势");
    }
    if (m2.tar != null && m2.tar > 1.5) {
        riskScore += 1;
        riskReasons.push("当前 θ/α 比值高于参考阈值");
    }
    if (aRP != null && aRP < 0.2) {
        riskScore += 1;
        riskReasons.push("Alpha 相对功率偏低");
    }
    var riskLabel = riskScore >= 3 ? "高" : riskScore >= 1 ? "中" : "低";
    var riskColor = riskScore >= 3 ? "#C0392B" : riskScore >= 1 ? "#B7791F" : "#4A7C3F";

    var adviceForDoctor, adviceForCaregiver;
    if (riskScore >= 3) {
        adviceForDoctor = "建议结合临床病史与影像学检查复核，考虑转介神经科专科评估；" +
            "关注 EEG 慢化是否伴随认知量表（CT-30）同步下滑，必要时调整干预强度或药物方案。";
        adviceForCaregiver = "老人近期脑电节律提示认知负荷偏重，建议适当减少单次训练时长、增加休息频次，" +
            "并留意日常生活中是否出现记忆力或定向力方面的新变化，及时与主管医生沟通。";
    } else if (riskScore >= 1) {
        adviceForDoctor = "存在轻度电生理慢化迹象，建议维持常规随访频率（每2-4周），" +
            "重点追踪 TAR 与 CT-30 的纵向变化趋势，暂不需调整治疗方案。";
        adviceForCaregiver = "整体脑电节律尚在可接受范围，建议保持规律训练（每周不少于3次），" +
            "训练前后关注老人的疲劳与情绪状态，配合系统的自动休息提示执行。";
    } else {
        adviceForDoctor = "未检测到明显的 EEG 慢化迹象，认知训练干预的电生理响应良好，建议维持现有方案并按期复评。";
        adviceForCaregiver = "老人脑电节律表现稳定，可继续按计划开展认知训练，保持良好作息与训练依从性。";
    }

    var conclusionHtml = '<h3>5.5 综合结论</h3>' +
        '<div class="conclusion-box">' +
        '<p class="concl-lead">基于本期 <b>' + psd.n + '</b> 条有效 EEG 试次、覆盖 <b>' + psd.sessions.length + '</b> 次训练会话的 Fp1 单通道节律分析，' +
        '综合 θ/α 比值走势、Alpha 相对功率及各任务域频段分布特征，形成如下结论：</p>' +
        '<p class="concl-item"><span class="concl-tag" style="background:' + riskColor + ';">风险等级：' + riskLabel + '</span>' +
        (riskReasons.length ? riskReasons.join("；") + "。" : "各项电生理标志物未见明显异常。") + '</p>' +
        '<p class="concl-item"><b>给临床医生：</b>' + adviceForDoctor + '</p>' +
        '<p class="concl-item"><b>给照护者/家属：</b>' + adviceForCaregiver + '</p>' +
        '<p class="concl-note">本结论由系统基于脑电节律数据自动生成，反映训练期间的电生理趋势，仅供临床参考，不构成诊断结论；' +
        '最终诊疗决策应结合患者病史、认知量表评估及影像学检查综合判断。</p>' +
        '</div>';

    return kpi + bandTable + taskTable + sessTable + interpret + conclusionHtml;
}

/* AI/CFI 跨会话趋势图（离屏高分辨率渲染） */
function _renderEEGTrendChart(sess) {
    var W = 820, H = 300, dpr = 3;
    var cv = document.createElement("canvas");
    cv.width = W * dpr; cv.height = H * dpr;
    var ctx = cv.getContext("2d");
    ctx.scale(dpr, dpr);

    var pad = {top: 36, right: 20, bottom: 44, left: 46};
    var cw = W - pad.left - pad.right, ch = H - pad.top - pad.bottom;
    var n = sess.length;

    ctx.fillStyle = "#FAF6F0";
    ctx.fillRect(0, 0, W, H);

    // 网格 0-100
    ctx.strokeStyle = "#E8E0D8";
    ctx.lineWidth = 0.5;
    ctx.font = "11px sans-serif";
    for (var i = 0; i <= 5; i++) {
        var v = i * 20;
        var y = pad.top + ch * (1 - v / 100);
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(pad.left + cw, y);
        ctx.stroke();
        ctx.fillStyle = "#9B8B7A";
        ctx.textAlign = "right";
        ctx.fillText(v.toString(), pad.left - 8, y + 4);
    }

    // 保护阈值线 (CFI 40/60/80)
    var thresholds = [
        {v: 40, c: "#D4A017", lab: "一级保护 CFI≥40"},
        {v: 60, c: "#E07A5F", lab: "二级保护 CFI≥60"},
        {v: 80, c: "#C0392B", lab: "三级保护 CFI≥80"}
    ];
    thresholds.forEach(function(th) {
        var y = pad.top + ch * (1 - th.v / 100);
        ctx.strokeStyle = th.c;
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 4]);
        ctx.globalAlpha = 0.55;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(pad.left + cw, y);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
        ctx.fillStyle = th.c;
        ctx.textAlign = "left";
        ctx.font = "10px sans-serif";
        ctx.fillText(th.lab, pad.left + 4, y - 3);
    });

    // X 轴标签
    ctx.textAlign = "center";
    ctx.fillStyle = "#9B8B7A";
    ctx.font = "11px sans-serif";
    var xAt = function(i) { return pad.left + (n === 1 ? cw / 2 : cw * i / (n - 1)); };
    for (var s = 0; s < n; s++) ctx.fillText("S" + sess[s].session, xAt(s), H - pad.bottom + 18);

    // 折线绘制
    var drawLine = function(key, color) {
        var vals = sess.map(function(x) { return x[key]; });
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.2;
        ctx.beginPath();
        var started = false;
        for (var i = 0; i < n; i++) {
            if (vals[i] == null) continue;
            var x = xAt(i), y = pad.top + ch * (1 - Math.min(100, Math.max(0, vals[i])) / 100);
            if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.fillStyle = color;
        for (var j = 0; j < n; j++) {
            if (vals[j] == null) continue;
            ctx.beginPath();
            ctx.arc(xAt(j), pad.top + ch * (1 - Math.min(100, Math.max(0, vals[j])) / 100), 3.5, 0, Math.PI * 2);
            ctx.fill();
        }
    };
    drawLine("ai", "#3D85C6");
    drawLine("cfi", "#E07A5F");

    // 图例
    ctx.font = "12px sans-serif";
    ctx.textAlign = "left";
    ctx.fillStyle = "#3D85C6";
    ctx.fillRect(pad.left, 12, 18, 3);
    ctx.fillText("AI 注意力指数", pad.left + 24, 18);
    ctx.fillStyle = "#E07A5F";
    ctx.fillRect(pad.left + 130, 12, 18, 3);
    ctx.fillText("CFI 综合疲劳指数", pad.left + 154, 18);

    return cv.toDataURL("image/png");
}

/* 生成 EEG 分析章节 HTML */
function _buildEEGSection(t, eeg) {
    var fmt = function(v, d) { return v == null ? "—" : v.toFixed(d === undefined ? 1 : d); };
    var pct = function(v) { return v == null ? "—" : (v * 100).toFixed(1) + "%"; };

    // KPI 卡片
    var kpi = '<div class="summary" style="grid-template-columns:repeat(5,1fr); margin-bottom:14px;">' +
        '<div class="sum-card"><div class="num">' + fmt(eeg.overall.alpha) + '</div><div class="lab">Alpha 均值 (μV²)</div></div>' +
        '<div class="sum-card"><div class="num">' + fmt(eeg.overall.theta) + '</div><div class="lab">Theta 均值 (μV²)</div></div>' +
        '<div class="sum-card"><div class="num">' + fmt(eeg.overall.tar, 2) + '</div><div class="lab">θ/α 比值均值</div></div>' +
        '<div class="sum-card"><div class="num" style="color:#3D85C6;">' + fmt(eeg.overall.ai) + '</div><div class="lab">AI 注意力均值</div></div>' +
        '<div class="sum-card"><div class="num" style="color:#E07A5F;">' + fmt(eeg.overall.cfi) + '</div><div class="lab">CFI 疲劳均值</div></div>' +
        '</div>';

    // 眨眼分布
    var bd = eeg.blinkDist;
    var blinkTotal = (bd.intentional || 0) + (bd.spontaneous || 0);
    var intentRate = blinkTotal ? bd.intentional / blinkTotal : null;
    var blinkHtml = '<div class="warn-item warn-ok" style="margin-bottom:14px;">' +
        '<b>意图眨眼通道</b>：全部 ' + eeg.overall.n + ' 试次中，有意眨眼 <b>' + (bd.intentional || 0) + '</b> 次、自发眨眼 <b>' + (bd.spontaneous || 0) + '</b> 次、无眨眼 <b>' + (bd.none || 0) + '</b> 次；' +
        '有意眨眼占比 <b>' + pct(intentRate) + '</b>，为系统应答确认的主要意图输出通道。' +
        '<div class="note">三级保护响应累计触发：一级(CFI≥40) ' + eeg.prot.l1 + ' 试次 · 二级(CFI≥60) ' + eeg.prot.l2 + ' 试次 · 三级(CFI≥80) ' + eeg.prot.l3 + ' 试次</div></div>';

    // 任务域 EEG 表
    var taskRows = eeg.taskStats.map(function(s) {
        return [_escHtml(s.name), s.n, pct(s.acc), fmt(s.alpha), fmt(s.theta), fmt(s.tar, 2),
                fmt(s.ai), fmt(s.cfi), s.rt != null ? Math.round(s.rt) : "—", pct(s.intentRate)];
    });
    var taskTable = '<h3>4.1 各认知任务域 EEG 指标</h3>' +
        _buildReportTable(taskRows,
            ["认知域", "试次数", "正确率", "Alpha(μV²)", "Theta(μV²)", "θ/α", "AI", "CFI", "RT(ms)", "有意眨眼率"],
            [null, "right", "right", "right", "right", "right", "right", "right", "right", "right"]) +
        '<p class="note">单通道 EEG（Fp1 前额导联）在五项认知任务下的频带功率与认知负荷指标对比，反映各认知域的神经资源投入差异。</p>';

    // 会话级趋势表
    var sessRows = eeg.sessions.map(function(s) {
        return ["S" + s.session, _escHtml((s.date || "").substring(0, 10)), s.n,
                fmt(s.alpha), fmt(s.theta), fmt(s.tar, 2), fmt(s.ai), fmt(s.cfi),
                pct(s.intentRate),
                (s.protL1 || s.protL2 || s.protL3) ? '<span class="down">' + s.protL1 + '/' + s.protL2 + '/' + s.protL3 + '</span>' : "0"];
    });
    var sessTable = '<h3>4.2 EEG 指标跨会话趋势</h3>' +
        _buildReportTable(sessRows,
            ["会话", "日期", "试次", "Alpha(μV²)", "Theta(μV²)", "θ/α", "AI", "CFI", "有意眨眼率", "保护触发 L1/L2/L3"],
            [null, null, "right", "right", "right", "right", "right", "right", "right", "center"]);

    // AI/CFI 趋势图
    var chartImg = '<h3>4.3 AI / CFI 跨会话趋势与三级保护阈值</h3>' +
        '<img class="chart-img" src="' + _renderEEGTrendChart(eeg.sessions) + '" alt="AI/CFI跨会话趋势">' +
        '<p class="note">AI（注意力指数）= P<sub>A</sub>/P<sub>T</sub> 经 Z-score 标准化；CFI（综合疲劳指数）= 0.4·ΔP<sub>A</sub> + 0.35·ΔR + 0.25·ΔSBR。虚线为 DMAP 三级保护响应阈值。</p>';

    // 相关性分析
    var corr = eeg.corr;
    var corrRows = [
        ["θ/α 比值 vs 答题正确率", fmt(corr.tarAcc, 3), _corrDesc(corr.tarAcc),
         "θ/α 升高提示困倦与认知负荷加重，预期与正确率负相关"],
        ["AI 注意力 vs 反应时间", fmt(corr.aiRt, 3), _corrDesc(corr.aiRt),
         "注意力水平越高，意图眨眼应答通常越迅速（负相关）"],
        ["AI 注意力 vs 答题正确率", fmt(corr.aiAcc, 3), _corrDesc(corr.aiAcc),
         "注意力资源投入与任务表现的耦合程度"],
        ["CFI 疲劳 vs 答题正确率", fmt(corr.cfiAcc, 3), _corrDesc(corr.cfiAcc),
         "疲劳累积对认知表现的损耗效应"]
    ];
    var corrTable = '<h3>4.4 EEG-行为相关性分析（试次级 Pearson r）</h3>' +
        _buildReportTable(corrRows, ["指标对", "r", "判定", "临床意义"], [null, "center", "center", null]) +
        '<p class="note">基于全部 ' + eeg.overall.n + ' 条逐试次记录计算；|r|&lt;0.1 几乎无相关，0.1-0.3 弱，0.3-0.5 中等，&gt;0.5 强。</p>';

    // 自动解读
    var bullets = [];
    var S = eeg.sessions;
    if (S.length >= 2) {
        var k = Math.max(1, Math.floor(S.length / 3));
        var earlyAI = _mean(S.slice(0, k).map(function(x) { return x.ai; }));
        var lateAI = _mean(S.slice(-k).map(function(x) { return x.ai; }));
        var earlyCFI = _mean(S.slice(0, k).map(function(x) { return x.cfi; }));
        var lateCFI = _mean(S.slice(-k).map(function(x) { return x.cfi; }));
        if (earlyAI != null && lateAI != null) {
            var dAI = lateAI - earlyAI;
            bullets.push("<b>注意力轨迹</b>：AI 均值由前期 " + fmt(earlyAI) + " 变化至近期 " + fmt(lateAI) +
                "（" + (dAI > 2 ? "上升" : dAI < -2 ? "下降" : "基本平稳") + "），" +
                (dAI > 2 ? "提示单通道 EEG 反映的皮层警觉水平随训练改善。" :
                 dAI < -2 ? "提示警觉水平走低，需结合 CFI 判断是否为疲劳累积所致。" :
                 "警觉水平维持稳定。"));
        }
        if (earlyCFI != null && lateCFI != null) {
            var dCFI = lateCFI - earlyCFI;
            bullets.push("<b>疲劳负荷</b>：CFI 均值由前期 " + fmt(earlyCFI) + " 变化至近期 " + fmt(lateCFI) +
                "（" + (dCFI > 5 ? "上升" : dCFI < -5 ? "下降" : "基本平稳") + "）；全期共触发二级保护 " + eeg.prot.l2 +
                " 试次、三级保护 " + eeg.prot.l3 + " 试次，" +
                (eeg.prot.l3 > 0 ? "存在明显认知耗竭时段，建议缩短单次训练时长。" :
                 eeg.prot.l2 > 0 ? "偶发疲劳峰值，系统已自动插入休息与降档。" : "未出现深度疲劳，训练负荷适配良好。"));
        }
    }
    if (eeg.overall.tar != null) {
        bullets.push("<b>θ/α 比值</b>：全期均值 " + fmt(eeg.overall.tar, 2) +
            "，θ/α 与正确率相关 r=" + fmt(corr.tarAcc, 3) + "（" + _corrDesc(corr.tarAcc) + "），" +
            (corr.tarAcc != null && corr.tarAcc < -0.1
                ? "印证慢波活动增强伴随任务表现下降，符合 AD 早期 EEG 慢化特征。"
                : "提示当前负荷下慢波活动对表现影响有限。"));
    }
    if (intentRate != null) {
        bullets.push("<b>意图眨眼输出</b>：有意眨眼占比 " + pct(intentRate) +
            "，与 AI 相关 r=" + fmt(corr.aiAcc, 3) + "；该指标反映患者经由单通道 EEG 眨眼应答通道参与干预的有效性。");
    }
    // 任务域 EEG 差异
    if (eeg.taskStats.length >= 2) {
        var maxCfi = eeg.taskStats.reduce(function(a, b) { return (b.cfi || 0) > (a.cfi || 0) ? b : a; });
        var minCfi = eeg.taskStats.reduce(function(a, b) { return (b.cfi || 0) < (a.cfi || 0) ? b : a; });
        if (maxCfi.cfi != null && minCfi.cfi != null && maxCfi.key !== minCfi.key) {
            bullets.push("<b>任务负荷差异</b>：CFI 最高的任务域为" + _escHtml(maxCfi.name) + "（" + fmt(maxCfi.cfi) +
                "），最低为" + _escHtml(minCfi.name) + "（" + fmt(minCfi.cfi) +
                "），建议对高负荷域适当降低难度档位或增加休息频次。");
        }
    }
    var interpretHtml = '<h3>4.5 EEG 应用分析解读</h3><ul class="eeg-bullets">' +
        bullets.map(function(b) { return "<li>" + b + "</li>"; }).join("") + "</ul>";

    return kpi + blinkHtml + taskTable + sessTable + chartImg + corrTable + interpretHtml;
}

async function downloadTrajectoryReport() {
    if (!_trajCache || !state.currentUser) { showToast("暂无轨迹数据，无法生成报告", "error"); return; }
    var btn = $("trajDownloadBtn");
    var t = _trajCache;
    var sufficient = t._sufficient;
    var uid = state.currentUser;
    btn.disabled = true;
    btn.textContent = "生成中…";

    try {
        // 1. 高分辨率捕获图表
        var imgs = _captureTrajCharts(t, sufficient);

        var now = new Date();
        var pad2 = function(v) { return v < 10 ? "0" + v : v; };
        var genTime = now.getFullYear() + "-" + pad2(now.getMonth() + 1) + "-" + pad2(now.getDate()) +
            " " + pad2(now.getHours()) + ":" + pad2(now.getMinutes());
        var dateTag = "" + now.getFullYear() + pad2(now.getMonth() + 1) + pad2(now.getDate());

        // 2. 概览
        var lastCT30 = t.total_scores[t.total_scores.length - 1];
        var firstCT30 = t.total_scores[0];
        var riskColor = t.risk_level === "高风险" ? "#C0392B" : t.risk_level === "关注" ? "#B7791F" : "#4A7C3F";

        // 3. 预警区
        var warnHtml;
        if (t.warnings && t.warnings.length) {
            warnHtml = t.warnings.map(function(w) {
                var lv = w.level === "high" ? "高风险" : "关注";
                var cls = w.level === "high" ? "warn-high" : "warn-mid";
                return '<div class="warn-item ' + cls + '"><span class="warn-lv">' + lv + '</span>' + _escHtml(w.message) + '</div>';
            }).join("");
        } else {
            warnHtml = '<div class="warn-item warn-ok"><span class="warn-lv">正常</span>未检测到风险模式</div>';
        }

        // 4. 轨迹分类
        var classRows = [];
        for (var d = 0; d < COG_KEYS.length; d++) {
            var k = COG_KEYS[d];
            var reg = (t.regressions || {})[k];
            classRows.push([
                _escHtml(COG_NAMES[d]),
                '<span class="trend-badge trend-' + t.trends[k] + '">' + TREND_LABELS[t.trends[k]] + '</span>',
                t.cog_vectors[0][d].toFixed(2),
                t.cog_vectors[t.cog_vectors.length - 1][d].toFixed(2),
                (sufficient && reg) ? reg.slope.toFixed(3) + " [" + reg.ci_low.toFixed(3) + ", " + reg.ci_high.toFixed(3) + "]" : "—"
            ]);
        }

        // 5. 会话明细表
        var sessionRows = [];
        for (var i = 0; i < t.raw_scores.length; i++) {
            var s = t.raw_scores[i];
            var row = [i + 1, t.session_labels[i] ? t.session_labels[i].substring(0, 16) : "-"];
            for (var c = 0; c < COG_KEYS.length; c++) row.push(s[COG_KEYS[c]].toFixed(1));
            var diff = i > 0 ? (t.total_scores[i] - t.total_scores[i - 1]) : null;
            row.push("<b>" + t.total_scores[i].toFixed(1) + "</b>");
            row.push(diff === null ? "—" : (diff > 0.5 ? '<span class="up">+' + diff.toFixed(1) + '</span>' :
                diff < -0.5 ? '<span class="down">' + diff.toFixed(1) + '</span>' : '<span class="flat">→</span>'));
            sessionRows.push(row);
        }

        // 6. 逐试次明细（全部会话）
        var trialHtml = "";
        if (t.trial_details && t.trial_details.length) {
            trialHtml = t.trial_details.map(function(det) {
                var trials = det.trials || [];
                if (!trials.length) return "";
                var rows = trials.map(function(tr, idx) {
                    return [
                        idx + 1,
                        _escHtml(TASK_KEY_NAMES[tr.task_key] || tr.task_key || "-"),
                        tr.is_correct ? '<span class="up">✓</span>' : '<span class="down">✗</span>',
                        _escHtml(BLINK_TYPE_LABELS[tr.blink_type] || tr.blink_type || "-"),
                        tr.intent_level >= 2 ? "强" : tr.intent_level === 1 ? "弱" : "-",
                        tr.reaction_time_ms != null ? tr.reaction_time_ms : "-",
                        tr.alpha_power != null ? tr.alpha_power.toFixed(1) : "-",
                        tr.theta_power != null ? tr.theta_power.toFixed(1) : "-",
                        tr.cfi_snapshot != null ? tr.cfi_snapshot.toFixed(1) : "-",
                        tr.ai_snapshot != null ? tr.ai_snapshot.toFixed(1) : "-"
                    ];
                });
                return '<h3>第 ' + det.session + ' 次会话（' + _escHtml((det.date || "").substring(0, 16)) + '）</h3>' +
                    _buildReportTable(rows,
                        ["#", "任务", "正确", "眨眼类型", "意图强度", "RT(ms)", "Alpha(μV²)", "Theta(μV²)", "CFI", "AI"],
                        [null, null, "center", null, "center", "right", "right", "right", "right", "right"]);
            }).join("");
        }

        // 6.5 单通道EEG应用分析
        var eeg = _analyzeEEG(t);
        var eegSection = eeg
            ? '<div class="pagebreak"></div>\n<h2 class="sec">四、单通道 EEG 应用分析</h2>\n' +
              '<p class="note" style="margin-bottom:12px;">基于 TGAM 单通道 EEG（Fp1 前额导联，采样率 512Hz）逐试次采集的 Alpha/Theta 频带功率、AI 注意力指数、CFI 综合疲劳指数与眨眼意图分类，进行多尺度统计分析。</p>\n' +
              _buildEEGSection(t, eeg)
            : '';

        // 6.6 频段节律与PSD分析（AD电生理标志物）
        var psd = _analyzePSD(t);
        var psdSection = psd
            ? '<div class="pagebreak"></div>\n<h2 class="sec">五、频段节律与 PSD 分析</h2>\n' +
              '<p class="note" style="margin-bottom:12px;">基于 Fp1 单通道 EEG 的 Delta/Theta/Alpha/Beta/Gamma 五频段功率谱密度，计算 θ/α 比值（TAR）、慢化指数（SI）等阿尔茨海默症电生理标志物，用于纵向追踪 EEG 慢化进程。</p>\n' +
              _buildPSDSection(psd)
            : '';

        // 7. 组装报告 HTML（自包含、可打印为 PDF）
        var alignR = [null, null, "right", "right", "right", "right", "right", "right", "right"];
        var html = '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n' +
            '<title>CTIS-EEG 认知轨迹报告 - ' + _escHtml(uid.name) + '</title>\n<style>\n' +
            '@page { size: A4; margin: 18mm 15mm; }\n' +
            '* { box-sizing: border-box; }\n' +
            'body { font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif; color: #2B2118; margin: 0; background: #fff; font-size: 13px; line-height: 1.6; }\n' +
            '.report { max-width: 860px; margin: 0 auto; padding: 32px 28px; }\n' +
            '.rpt-header { border-bottom: 3px solid #B0713F; padding-bottom: 16px; margin-bottom: 24px; }\n' +
            '.rpt-title { font-size: 26px; font-weight: 700; color: #6B3A1F; margin: 0 0 4px; }\n' +
            '.rpt-sub { color: #8A7A6A; font-size: 13px; }\n' +
            '.meta-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 16px 0 8px; }\n' +
            '.meta-item { background: #FAF6F0; border: 1px solid #EADFCF; border-radius: 8px; padding: 10px 12px; }\n' +
            '.meta-item .k { font-size: 11px; color: #8A7A6A; }\n' +
            '.meta-item .v { font-size: 15px; font-weight: 700; color: #3D2C1E; word-break: break-all; }\n' +
            'h2.sec { font-size: 17px; color: #6B3A1F; border-left: 4px solid #B0713F; padding-left: 10px; margin: 28px 0 12px; page-break-after: avoid; }\n' +
            'h3 { font-size: 14px; color: #3D2C1E; margin: 18px 0 8px; page-break-after: avoid; }\n' +
            '.summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }\n' +
            '.sum-card { border: 1px solid #EADFCF; border-radius: 10px; padding: 14px; text-align: center; background: #FDFBF7; }\n' +
            '.sum-card .num { font-size: 24px; font-weight: 800; color: #6B3A1F; }\n' +
            '.sum-card .lab { font-size: 12px; color: #8A7A6A; margin-top: 2px; }\n' +
            '.warn-item { border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; border: 1px solid; page-break-inside: avoid; }\n' +
            '.warn-high { background: #FDECEA; border-color: #E5B4AE; }\n' +
            '.warn-mid { background: #FDF6E3; border-color: #E0CE9A; }\n' +
            '.warn-ok { background: #EDF5EA; border-color: #BBD3B2; }\n' +
            '.warn-lv { display: inline-block; font-size: 11px; font-weight: 700; padding: 1px 8px; border-radius: 10px; background: rgba(0,0,0,0.08); margin-right: 8px; }\n' +
            'table { width: 100%; border-collapse: collapse; margin: 8px 0 4px; font-size: 12px; }\n' +
            'th { background: #F0E7DA; color: #5C4A3A; font-weight: 700; padding: 7px 8px; border: 1px solid #DFD2BF; text-align: left; }\n' +
            'td { padding: 6px 8px; border: 1px solid #E6DCCB; }\n' +
            'tbody tr:nth-child(even) { background: #FBF8F3; }\n' +
            'thead { display: table-header-group; }\n' +
            'tr { page-break-inside: avoid; }\n' +
            '.up { color: #4A7C3F; font-weight: 700; }\n' +
            '.down { color: #C0392B; font-weight: 700; }\n' +
            '.flat { color: #8A7A6A; }\n' +
            '.trend-badge { display: inline-block; color: #fff; font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 10px; }\n' +
            '.trend-improving { background: #6A994E; }\n' +
            '.trend-stable { background: #9B8B7A; }\n' +
            '.trend-declining { background: #E07A5F; }\n' +
            '.chart-img { width: 100%; border: 1px solid #EADFCF; border-radius: 8px; margin: 6px 0 14px; page-break-inside: avoid; }\n' +
            '.chart-2col { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }\n' +
            '.chart-2col img { width: 100%; border: 1px solid #EADFCF; border-radius: 8px; page-break-inside: avoid; }\n' +
            '.report-pre { background: #FAF6F0; border: 1px solid #EADFCF; border-radius: 10px; padding: 18px 20px; white-space: pre-wrap; font-family: "Microsoft YaHei", "PingFang SC", sans-serif; font-size: 13px; line-height: 1.9; color: #3D2C1E; page-break-inside: auto; }\n' +
            '.note { font-size: 11px; color: #8A7A6A; margin-top: 4px; }\n' +
            '.conclusion-box { background: #FDFBF7; border: 1px solid #DFD2BF; border-left: 5px solid #B0713F; border-radius: 10px; padding: 18px 22px; page-break-inside: avoid; }\n' +
            '.concl-lead { margin: 0 0 12px; color: #3D2C1E; }\n' +
            '.concl-item { margin: 0 0 10px; color: #3D2C1E; }\n' +
            '.concl-tag { display: inline-block; color: #fff; font-weight: 700; font-size: 12px; padding: 2px 12px; border-radius: 12px; margin-right: 8px; }\n' +
            '.concl-note { margin: 12px 0 0; font-size: 11px; color: #8A7A6A; border-top: 1px dashed #E6DCCB; padding-top: 10px; }\n' +
            '.eeg-bullets { margin: 8px 0; padding-left: 20px; }\n' +
            '.eeg-bullets li { margin-bottom: 10px; page-break-inside: avoid; background: #FBF8F3; border: 1px solid #EADFCF; border-radius: 8px; padding: 10px 14px; list-style-position: inside; }\n' +
            '.rpt-footer { margin-top: 36px; border-top: 1px solid #E6DCCB; padding-top: 12px; font-size: 11px; color: #8A7A6A; display: flex; justify-content: space-between; }\n' +
            '.pagebreak { page-break-before: always; }\n' +
            '.toolbar { max-width: 860px; margin: 0 auto; padding: 12px 28px; text-align: right; }\n' +
            '.toolbar button { background: #B0713F; color: #fff; border: none; border-radius: 8px; padding: 8px 18px; font-size: 13px; cursor: pointer; }\n' +
            '@media print { .toolbar { display: none; } body { font-size: 12px; } .report { padding: 0; max-width: none; } }\n' +
            '</style>\n</head>\n<body>\n' +
            '<div class="toolbar"><button onclick="window.print()">🖨 打印 / 另存为 PDF</button></div>\n' +
            '<div class="report">\n' +
            '<div class="rpt-header">\n' +
            '  <div class="rpt-title">CTIS-EEG 认知轨迹报告</div>\n' +
            '  <div class="rpt-sub">基于单通道EEG与意图眨眼的阿尔茨海默症认知训练与干预系统 · CSTM 跨会话认知轨迹建模</div>\n' +
            '  <div class="meta-grid">\n' +
            '    <div class="meta-item"><div class="k">用户姓名</div><div class="v">' + _escHtml(uid.name) + '</div></div>\n' +
            '    <div class="meta-item"><div class="k">用户编号</div><div class="v">' + _escHtml(uid.user_id) + '</div></div>\n' +
            '    <div class="meta-item"><div class="k">报告生成时间</div><div class="v">' + genTime + '</div></div>\n' +
            '    <div class="meta-item"><div class="k">建模条件</div><div class="v">' + (sufficient ? "满足（≥8次）" : "数据积累中") + '</div></div>\n' +
            '  </div>\n' +
            '</div>\n' +
            '<h2 class="sec">一、认知档案概览</h2>\n' +
            '<div class="summary">\n' +
            '  <div class="sum-card"><div class="num">' + t.session_count + '</div><div class="lab">总会话数</div></div>\n' +
            '  <div class="sum-card"><div class="num">' + lastCT30.toFixed(1) + '</div><div class="lab">最近 CT-30 总分</div></div>\n' +
            '  <div class="sum-card"><div class="num">' + _escHtml(t.overall_trend) + '</div><div class="lab">总体轨迹</div></div>\n' +
            '  <div class="sum-card"><div class="num" style="color:' + riskColor + ';">' + _escHtml(t.risk_level) + '</div><div class="lab">风险等级</div></div>\n' +
            '</div>\n' +
            '<p class="note">CT-30 首次 ' + firstCT30.toFixed(1) + ' 分 → 最近 ' + lastCT30.toFixed(1) + ' 分' +
            (sufficient && t.total_regression ? '；线性斜率 β₁=' + t.total_regression.slope.toFixed(3) +
                '（95%CI [' + t.total_regression.ci_low.toFixed(3) + ', ' + t.total_regression.ci_high.toFixed(3) + ']）' : '') + '</p>\n' +
            '<h2 class="sec">二、CSTM 认知预警</h2>\n' + warnHtml + '\n' +
            '<h2 class="sec">三、五维认知轨迹图表</h2>\n' +
            '<h3>3.1 五维认知向量轨迹（D1-D5，归一化 0-1）</h3>\n' +
            '<img class="chart-img" src="' + imgs.trajLineChart + '" alt="五维认知向量轨迹">\n' +
            '<h3>3.2 CT-30 总分轨迹</h3>\n' +
            '<img class="chart-img" src="' + imgs.trajTotalChart + '" alt="CT-30总分轨迹">\n' +
            '<div class="chart-2col">\n' +
            '  <div><h3>3.3 认知雷达图（首次 vs 最近）</h3><img src="' + imgs.trajRadarChart + '" alt="认知雷达图"></div>\n' +
            '  <div><h3>3.4 DMAP 状态空间（AI-CFI 四象限）</h3><img src="' + imgs.trajDmapChart + '" alt="DMAP状态空间"></div>\n' +
            '</div>\n' +
            eegSection + '\n' +
            psdSection + '\n' +
            '<h2 class="sec">六、五维轨迹分类</h2>\n' +
            (sufficient
                ? _buildReportTable(classRows, ["认知域", "轨迹分类", "首次得分", "最近得分", "β₁ (95%CI)"], [null, "center", "right", "right", "center"])
                : '<p class="note">需要至少 8 次会话数据才能生成轨迹分类。</p>') + '\n' +
            '<h2 class="sec">七、阶段性报告</h2>\n' +
            '<div class="report-pre">' + _escHtml(t.report) + '</div>\n' +
            '<div class="pagebreak"></div>\n' +
            '<h2 class="sec">八、会话明细（CT-30 各分项得分）</h2>\n' +
            _buildReportTable(sessionRows,
                ["会话", "日期", "D1定向力", "D2情景记忆", "D3执行功能", "D4语义记忆", "D5命名能力", "CT-30", "变化"],
                alignR) + '\n' +
            (trialHtml
                ? '<div class="pagebreak"></div>\n<h2 class="sec">九、逐试次数据维度明细</h2>\n<p class="note">含眨眼类型、意图强度、反应时间、EEG 频带功率及 CFI/AI 快照（说明书 8.1 表7）</p>\n' + trialHtml
                : '') + '\n' +
            '<div class="rpt-footer">\n' +
            '  <span>CTIS-EEG 认知训练与干预系统 · 自动生成报告</span>\n' +
            '  <span>生成时间：' + genTime + '</span>\n' +
            '</div>\n' +
            '</div>\n</body>\n</html>';

        // 8. 触发下载
        var blob = new Blob(["\ufeff", html], {type: "text/html;charset=utf-8"});
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = "CTIS-EEG认知轨迹报告_" + uid.name + "_" + dateTag + ".html";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(function() { URL.revokeObjectURL(url); }, 10000);

        showToast("报告已下载，用浏览器打开后可点击“打印/另存为 PDF”", "success");
    } catch (e) {
        console.error("报告生成失败", e);
        showToast("报告生成失败: " + e.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "⬇ 下载报告";
    }
}

/* ============== 启动 ============== */
tryAutoLogin();
updateControlModeUI();

/* ============== 设置面板 ============== */
function toggleSettings() {
    var panel = $("settingsPanel");
    var overlay = $("settingsOverlay");
    var isOpen = panel.classList.contains("active");
    if (isOpen) {
        panel.classList.remove("active");
        overlay.classList.remove("active");
    } else {
        // 打开时同步当前阈值到滑块
        loadThresholdsToUI();
        panel.classList.add("active");
        overlay.classList.add("active");
    }
}

function closeSettings() {
    $("settingsPanel").classList.remove("active");
    $("settingsOverlay").classList.remove("active");
}

function onThresholdChange() {
    $("thBaseVal").textContent = $("thBaseSlider").value;
    $("thMidVal").textContent = $("thMidSlider").value;
    $("thStrongVal").textContent = $("thStrongSlider").value;
}

function loadThresholdsToUI() {
    // 从后端获取当前阈值
    fetch(API + "/api/device/status").then(function(r) { return r.json(); }).then(function(data) {
        var t = data.thresholds || {base: 80, mid: 150, strong: 250};
        $("thBaseSlider").value = t.base;
        $("thMidSlider").value = t.mid;
        $("thStrongSlider").value = t.strong;
        $("thBaseVal").textContent = t.base;
        $("thMidVal").textContent = t.mid;
        $("thStrongVal").textContent = t.strong;
    });
}

async function saveThresholds() {
    var base = parseInt($("thBaseSlider").value);
    var mid = parseInt($("thMidSlider").value);
    var strong = parseInt($("thStrongSlider").value);
    // 校验：弱 < 中 < 强
    if (base >= mid || mid >= strong) {
        showToast("阈值需满足：弱 < 中 < 强", "error");
        return;
    }
    var res = await fetch(API + "/api/device/thresholds", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({base: base, mid: mid, strong: strong})
    });
    var data = await res.json();
    if (data.ok) {
        showToast("阈值已保存", "success");
        closeSettings();
    } else {
        showToast(data.msg || "保存失败", "error");
    }
}

/* ============== 题库管理 ============== */
var _qbankCache = null;  // 缓存当前题库数据
var _qbankEditItem = null;  // 当前编辑的题目

function initQbank() {
    if (!state.currentUser) { showToast("请先登录", "error"); return; }
    var taskList = $("qbankTaskList");
    var taskEmojis = {orient:"🧭", memencode:"📖", trailblink:"🔗", semflow:"🏷️", nameblink:"💬"};
    var taskNames = {orient:"定向力", memencode:"情景记忆", trailblink:"执行功能", semflow:"语义记忆", nameblink:"命名能力"};
    var html = "";
    for (var key in taskNames) {
        html += '<button class="btn btn-ghost" style="font-size:14px;" onclick="loadQbankTask(\'' + key + '\')">' +
            (taskEmojis[key] || "") + " " + taskNames[key] + '</button>';
    }
    taskList.innerHTML = html;
    $("qbankContent").style.display = "none";
}

async function loadQbankTask(taskKey) {
    var userId = state.currentUser.user_id;
    var res = await fetch(API + "/api/qbank/" + taskKey + "?user_id=" + userId);
    var data = await res.json();
    if (!data.ok) { showToast(data.msg || "加载失败", "error"); return; }

    _qbankCache = data;
    $("qbankContent").style.display = "block";
    $("qbankTaskTitle").textContent = data.task_name;

    // 填充场景选择
    var sel = $("qbankSceneSelect");
    sel.innerHTML = "";
    data.scenes.forEach(function(s, i) {
        var opt = document.createElement("option");
        opt.value = i;
        opt.textContent = s.scene_name;
        sel.appendChild(opt);
    });
    loadQbankScene();
}

function loadQbankScene() {
    if (!_qbankCache) return;
    var sceneIdx = parseInt($("qbankSceneSelect").value);
    var scene = _qbankCache.scenes[sceneIdx];
    if (!scene) return;

    var domainLabels = {time: "时间定向", knowledge: "常识定向", place: "地点定向", "": "通用"};
    var html = "";
    scene.trials.forEach(function(t, i) {
        var opts = t.is_modified && t.custom_options ? t.custom_options : t.options;
        var ansIdx = t.is_modified && t.custom_answer !== null ? t.custom_answer : t.answer;
        var modBadge = t.is_modified ? '<span style="background:#E07A5F; color:white; font-size:11px; padding:2px 6px; border-radius:4px; margin-left:6px;">已修改</span>' : '';
        var domainLabel = domainLabels[t.domain] || t.domain || "通用";

        html += '<div class="card" style="margin-bottom:10px; padding:14px;">';
        html += '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">';
        html += '<div><b style="font-size:14px;">第' + (i + 1) + '题</b> <span class="text-soft" style="font-size:12px;">[' + domainLabel + ']</span>' + modBadge + '</div>';
        html += '<button class="btn btn-ghost" style="font-size:12px; padding:4px 10px;" onclick="openQbankEdit(' + sceneIdx + ',' + i + ')">编辑</button>';
        html += '</div>';
        html += '<div style="font-size:15px; margin-bottom:8px;">' + t.prompt + '</div>';
        html += '<div style="display:flex; gap:8px; flex-wrap:wrap;">';
        if (opts && opts.length > 0) {
            opts.forEach(function(o, oi) {
                var isAns = (oi === ansIdx);
                var style = isAns
                    ? 'background:#6A994E; color:white; padding:4px 12px; border-radius:6px; font-size:13px; font-weight:600;'
                    : 'background:var(--bg-soft); color:var(--text-main); padding:4px 12px; border-radius:6px; font-size:13px;';
                html += '<span style="' + style + '">' + o + (isAns ? ' ✓' : '') + '</span>';
            });
        } else {
            html += '<span class="text-soft" style="font-size:13px;">（动态生成，无需预设选项）</span>';
        }
        html += '</div></div>';
    });
    $("qbankTrialsList").innerHTML = html;
}

function openQbankEdit(sceneIdx, trialIdx) {
    var scene = _qbankCache.scenes[sceneIdx];
    var t = scene.trials[trialIdx];
    _qbankEditItem = {sceneIdx: sceneIdx, trialIdx: trialIdx, trial: t};

    $("qbankEditPrompt").value = t.prompt;
    $("qbankEditDomain").value = t.domain || "通用";

    var opts = t.is_modified && t.custom_options ? t.custom_options : t.options;
    var ansIdx = t.is_modified && t.custom_answer !== null ? t.custom_answer : t.answer;

    var optHtml = '<label style="font-size:14px; font-weight:600; margin-bottom:8px; display:block;">选项（点击圆圈标记正确答案）</label>';
    if (opts && opts.length > 0) {
        opts.forEach(function(o, i) {
            var checked = (i === ansIdx) ? "checked" : "";
            optHtml += '<div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">';
            optHtml += '<input type="radio" name="qbankAnswer" value="' + i + '" ' + checked + ' style="accent-color:#6A994E;">';
            optHtml += '<input class="input qbank-opt-input" data-idx="' + i + '" value="' + o + '" style="flex:1;">';
            optHtml += '</div>';
        });
    } else {
        optHtml += '<p class="text-soft">该题目选项为动态生成，无法在此编辑</p>';
    }
    $("qbankEditOptions").innerHTML = optHtml;

    $("qbankEditModal").style.display = "flex";
}

function closeQbankEdit() {
    $("qbankEditModal").style.display = "none";
    _qbankEditItem = null;
}

async function saveQbankEdit() {
    if (!_qbankEditItem) return;
    var t = _qbankEditItem.trial;
    var optInputs = document.querySelectorAll(".qbank-opt-input");
    var newOptions = [];
    optInputs.forEach(function(inp) { newOptions.push(inp.value.trim()); });
    if (newOptions.some(function(o) { return !o; })) {
        showToast("选项不能为空", "error"); return;
    }
    var ansRadio = document.querySelector('input[name="qbankAnswer"]:checked');
    if (!ansRadio) { showToast("请选择正确答案", "error"); return; }
    var newAnswer = parseInt(ansRadio.value);

    var userId = state.currentUser.user_id;
    var res = await fetch(API + "/api/qbank/" + _qbankCache.task_key + "/update", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            user_id: userId,
            scene_name: t.scene_name,
            prompt: t.prompt,
            domain: t.domain || "",
            original_options: t.options,
            original_answer: t.answer,
            custom_options: newOptions,
            custom_answer: newAnswer,
        })
    });
    var data = await res.json();
    if (data.ok) {
        showToast("保存成功", "success");
        closeQbankEdit();
        loadQbankTask(_qbankCache.task_key);  // 刷新
    } else {
        showToast(data.msg || "保存失败", "error");
    }
}

async function resetQbankEdit() {
    if (!_qbankEditItem) return;
    var t = _qbankEditItem.trial;
    var userId = state.currentUser.user_id;
    var res = await fetch(API + "/api/qbank/" + _qbankCache.task_key + "/reset", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            user_id: userId,
            scene_name: t.scene_name,
            prompt: t.prompt,
        })
    });
    var data = await res.json();
    if (data.ok) {
        showToast("已恢复默认", "success");
        closeQbankEdit();
        loadQbankTask(_qbankCache.task_key);
    } else {
        showToast(data.msg || "恢复失败", "error");
    }
}
