(function () {
  "use strict";

  function $(id) {
    return document.getElementById(id);
  }

  var srcLang = $("src-lang");
  var tgtLang = $("tgt-lang");
  var srcText = $("src-text");
  var tgtText = $("tgt-text");
  var charCount = $("char-count");
  var btnSwap = $("btn-swap");
  var btnClear = $("btn-clear");
  var btnCopy = $("btn-copy");
  var btnTranslate = $("btn-translate");
  var statusEl = $("status");
  var progressEl = $("progress");
  var progressFill = progressEl.querySelector(".fill");
  var dropzone = $("dropzone");
  var fileInput = $("file-input");
  var fileResult = $("file-result");
  var fileResultMsg = $("file-result-msg");
  var fileDlBtn = $("file-dl-btn");
  var fileError = $("file-error");
  var timer = null;
  var lastTranslated = "";

  function setStatus(msg, kind) {
    statusEl.textContent = msg || "";
    statusEl.className = "translate-status" + (kind ? " " + kind : "");
  }

  function setFileError(msg) {
    fileError.textContent = msg || "";
    fileError.className = "file-error" + (msg ? " visible" : "");
  }

  function updateCount() {
    charCount.textContent = String((srcText.value || "").length);
  }

  function copyText(text, btnEl) {
    if (!text) return;
    var done = function () {
      var orig = btnEl.textContent;
      btnEl.textContent = "已复制";
      setTimeout(function () { btnEl.textContent = orig; }, 1500);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text, done); });
    } else {
      fallbackCopy(text, done);
    }
  }

  function fallbackCopy(text, done) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); done(); } catch (e) { /* 剪贴板不可用 */ }
    document.body.removeChild(ta);
  }

  function downloadTranslated(name) {
    if (!lastTranslated) return;
    var blob = new Blob([lastTranslated], { type: "text/plain;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = name || "translated.txt";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function tickProgress() {
    var sec = Math.floor((Date.now() - startAt) / 1000);
    var pct = Math.min(95, 10 + sec * 0.2);
    progressFill.style.width = pct + "%";
    if (sec < 30) {
      setStatus("正在加载翻译模型并排队... " + sec + "s", "");
    } else if (sec < 300) {
      setStatus("正在本地翻译，长文本可能需要数分钟... " + sec + "s", "");
    } else {
      setStatus("长文翻译中，请继续等待... " + sec + "s", "");
    }
  }

  var startAt = 0;

  function submitText() {
    var text = (srcText.value || "").trim();
    if (!text) {
      setStatus("请输入要翻译的文本", "error");
      return;
    }
    if (srcLang.value === tgtLang.value) {
      setStatus("源语言与目标语言相同", "error");
      return;
    }

    btnTranslate.disabled = true;
    btnTranslate.textContent = "翻译中...";
    progressEl.className = "file-translate-progress visible";
    progressFill.style.width = "10%";
    tgtText.value = "";
    startAt = Date.now();
    timer = setInterval(tickProgress, 1000);
    setStatus("正在本地翻译，请稍候...", "");

    fetch("/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: text,
        src_lang: srcLang.value,
        tgt_lang: tgtLang.value,
      }),
    })
      .then(function (resp) {
        return resp.text().then(function (body) {
          var data; try { data = JSON.parse(body); } catch (_) { data = {}; }
          if (!resp.ok) throw new Error(data.detail || "翻译失败（HTTP " + resp.status + "）");
          return data;
        });
      })
      .then(function (data) {
        tgtText.value = data.translated || "";
        lastTranslated = data.translated || "";
        progressFill.style.width = "100%";
        setStatus("翻译完成", "success");
      })
      .catch(function (err) {
        setStatus((err && err.message) ? err.message : "翻译失败", "error");
      })
      .then(function () {
        if (timer) clearInterval(timer);
        btnTranslate.disabled = false;
        btnTranslate.textContent = "翻译";
        setTimeout(function () {
          progressEl.className = "file-translate-progress";
          progressFill.style.width = "0";
        }, 800);
      });
  }

  function loadTxt(file) {
    if (!/\.txt$/i.test(file.name || "") && file.type !== "text/plain") {
      setFileError("请选择 TXT 文本文件。图片或 PDF 请先在 OCR 页识别。");
      setStatus("文件类型不支持", "error");
      return;
    }
    var reader = new FileReader();
    reader.onload = function () {
      var content = String(reader.result || "");
      srcText.value = content;
      updateCount();
      setStatus("已载入 " + file.name + "，共 " + content.length + " 字符", "success");
      setFileError("");
      fileResultMsg.textContent = "已载入 " + file.name;
      fileResult.className = "file-result visible";
      fileDlBtn.hidden = true;
    };
    reader.onerror = function () {
      setFileError("读取文件失败");
      setStatus("读取文件失败", "error");
    };
    reader.readAsText(file);
  }

  srcText.addEventListener("input", updateCount);
  btnClear.addEventListener("click", function () {
    srcText.value = "";
    tgtText.value = "";
    lastTranslated = "";
    updateCount();
    setStatus("");
    setFileError("");
    fileResult.className = "file-result";
    fileDlBtn.hidden = true;
  });
  btnCopy.addEventListener("click", function () { copyText(tgtText.value, btnCopy); });
  btnSwap.addEventListener("click", function () {
    var s = srcLang.value;
    srcLang.value = tgtLang.value;
    tgtLang.value = s;
    if (tgtText.value) {
      srcText.value = tgtText.value;
      tgtText.value = "";
      updateCount();
    }
  });
  btnTranslate.addEventListener("click", submitText);

  dropzone.addEventListener("click", function () { fileInput.click(); });
  fileInput.addEventListener("change", function () {
    if (fileInput.files && fileInput.files[0]) loadTxt(fileInput.files[0]);
    fileInput.value = "";
  });
  ["dragenter", "dragover"].forEach(function (evt) {
    dropzone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach(function (evt) {
    dropzone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });
  dropzone.addEventListener("drop", function (e) {
    if (e.dataTransfer.files && e.dataTransfer.files[0]) loadTxt(e.dataTransfer.files[0]);
  });

  fileDlBtn.addEventListener("click", function () {
    downloadTranslated("translated.txt");
  });

  srcText.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") submitText();
  });

  updateCount();
})();
