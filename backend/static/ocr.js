(function () {
  "use strict";

  function $(id) {
    return document.getElementById(id);
  }

  var tabFile = $("tabFile"), tabUrl = $("tabUrl");
  var panelFile = $("panelFile"), panelUrl = $("panelUrl");
  var dropZone = $("dropZone"), fileInput = $("fileInput");
  var fileInfo = $("fileInfo"), fileNameEl = $("fileName"), fileSizeEl = $("fileSize");
  var thumbEl = $("thumb"), fileIconEl = $("fileIcon"), fileRemove = $("fileRemove");
  var urlInput = $("urlInput");
  var fmtBoxes = Array.prototype.slice.call(document.querySelectorAll(".fmt"));
  var btn = $("ocrBtn"), previewBtn = $("previewBtn"), copyAllBtn = $("copyAllBtn"), resetBtn = $("resetBtn");
  var statusEl = $("status"), progressEl = $("progress"), progressFill = $("progressFill");
  var resultEl = $("result"), reportEl = $("report");
  var textEl = $("ocrText"), emptyEl = $("emptyNote");
  var copyBtn = $("copyBtn");
  var dlSec = $("downloadsSec"), dlList = $("dlList");
  var maskEl = $("previewMask"), tabsEl = $("previewTabs"), bodyEl = $("previewBody"), subEl = $("previewSub");
  var previewCloseBtn = $("previewClose");

  var MAX_BYTES = 50 * 1024 * 1024;
  var srcMode = "file";
  var selectedFile = null;
  var previewURL = null;
  var lastData = null;
  var lastText = "";
  var lastMarkdown = "";
  var startAt = 0;
  var tickTimer = null;

  var FMT_NAMES = { txt: "TXT", docx: "Word", xlsx: "Excel", pdf: "PDF", json: "JSON" };

  function fmtSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  function setStatus(msg, kind) {
    statusEl.textContent = msg || "";
    statusEl.className = "ocr-status" + (kind ? " " + kind : "");
  }

  function setSrcMode(mode) {
    srcMode = mode;
    tabFile.className = "tab-btn" + (mode === "file" ? " active" : "");
    tabUrl.className = "tab-btn" + (mode === "url" ? " active" : "");
    panelFile.className = "ocr-src-panel" + (mode === "file" ? " active" : "");
    panelUrl.className = "ocr-src-panel" + (mode === "url" ? " active" : "");
    setStatus("", "");
  }

  function showFile(file) {
    if (previewURL) {
      URL.revokeObjectURL(previewURL);
      previewURL = null;
    }
    if (!file) {
      clearFile();
      return;
    }
    if (file.size > MAX_BYTES) {
      setStatus("文件超过 50MB 限制，请更换文件", "error");
      return;
    }
    selectedFile = file;
    fileInfo.className = "ocr-file-info visible";
    fileNameEl.textContent = file.name;
    fileSizeEl.textContent = fmtSize(file.size);

    var isImage =
      (file.type && file.type.indexOf("image/") === 0) ||
      /\.(png|jpe?g|bmp|webp|tiff?)$/i.test(file.name || "");
    if (isImage) {
      previewURL = URL.createObjectURL(file);
      thumbEl.src = previewURL;
      thumbEl.hidden = false;
      fileIconEl.style.display = "none";
    } else {
      thumbEl.hidden = true;
      thumbEl.removeAttribute("src");
      fileIconEl.style.display = "inline";
      fileIconEl.textContent = "PDF";
    }

    dropZone.className = "ocr-drop has-file";
    dropZone.querySelector(".drop-text").textContent = "已选择文件，点击更换";
    dropZone.querySelector(".drop-hint").textContent = "可点击此处或下方移除按钮重新选择";
    setStatus("", "");
  }

  function clearFile() {
    if (previewURL) {
      URL.revokeObjectURL(previewURL);
      previewURL = null;
    }
    selectedFile = null;
    fileInput.value = "";
    fileInfo.className = "ocr-file-info";
    thumbEl.hidden = true;
    thumbEl.removeAttribute("src");
    fileIconEl.style.display = "inline";
    dropZone.className = "ocr-drop";
    dropZone.querySelector(".drop-text").textContent = "点击选择文件 或 拖拽到此处";
    dropZone.querySelector(".drop-hint").textContent =
      "支持 PNG · JPG · BMP · WEBP · TIF · PDF，单文件不超过 50MB";
    setStatus("", "");
  }

  function selectedFormats() {
    var out = [];
    fmtBoxes.forEach(function (b) {
      if (b.checked) out.push(b.value);
    });
    return out.length ? out : ["txt"];
  }

  function addBadge(label, value, key) {
    var span = document.createElement("span");
    span.className = "ocr-badge" + (key ? " key" : "");
    span.textContent = label + ": " + value;
    reportEl.appendChild(span);
  }

  function renderDownloads(taskId, formats) {
    dlList.textContent = "";
    formats.forEach(function (fmt) {
      var a = document.createElement("a");
      a.className = "ocr-dl";
      if (fmt === "txt" || fmt === "json") {
        a.href = "#";
        a.addEventListener("click", function (e) {
          e.preventDefault();
          if (fmt === "txt") downloadBlob(lastText, "ocr_result.txt", "text/plain;charset=utf-8");
          else downloadBlob(JSON.stringify(lastData, null, 2), "ocr_result.json", "application/json");
        });
      } else {
        a.href = "/api/export/" + encodeURIComponent(taskId) + "?format=" + encodeURIComponent(fmt);
      }
      a.textContent = FMT_NAMES[fmt] || fmt;
      dlList.appendChild(a);
    });
    dlSec.hidden = false;
  }

  function downloadBlob(text, name, type) {
    var blob = new Blob([text], { type: type });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function hideResult() {
    resultEl.className = "ocr-result";
    textEl.value = "";
    reportEl.textContent = "";
    dlList.textContent = "";
    emptyEl.hidden = true;
    emptyEl.textContent = "";
    dlSec.hidden = true;
    lastData = null;
    lastText = "";
    lastMarkdown = "";
    previewBtn.disabled = true;
    copyAllBtn.disabled = true;
    copyBtn.style.display = "";
    closePreview();
    progressEl.className = "ocr-progress";
    progressFill.style.width = "0";
  }

  function showResult(data) {
    lastData = data;
    lastText = data.text || "";
    lastMarkdown = data.markdown || data.text || "";
    var fmts = selectedFormats();
    resultEl.className = "ocr-result visible";
    reportEl.textContent = "";
    addBadge("页数", data.page_count || 1, true);
    addBadge("字符数", (lastText || "").length, true);
    addBadge("引擎", "PP-StructureV3");
    addBadge("识别模型", "PP-OCRv6_" + (data.ocr_model || "small"));
    addBadge("导出格式", fmts.map(function (f) { return FMT_NAMES[f] || f; }).join(" / "), true);

    if (lastText) {
      textEl.value = lastText;
      emptyEl.hidden = true;
      copyBtn.style.display = "";
      previewBtn.disabled = false;
      copyAllBtn.disabled = false;
    } else {
      textEl.value = "";
      emptyEl.hidden = false;
      emptyEl.textContent = "未识别到文字。请尝试更清晰的图片或 PDF。";
      copyBtn.style.display = "none";
      previewBtn.disabled = true;
      copyAllBtn.disabled = true;
    }

    if (data.task_id) renderDownloads(data.task_id, fmts);
  }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  function tableFromHtml(html) {
    var wrap = document.createElement("div");
    wrap.innerHTML = html || "";
    var table = wrap.querySelector("table");
    if (table) {
      table.className = "ocr-pv-table";
      return table;
    }
    return el("p", null, html || "");
  }

  function emptyNote(wrap) {
    wrap.appendChild(el("div", "ocr-pv-empty", "未识别到内容"));
    return wrap;
  }

  function renderTxt() {
    var wrap = el("div");
    if (!lastText) return emptyNote(wrap);
    wrap.appendChild(el("pre", "ocr-pv-pre", lastText));
    return wrap;
  }

  function renderDocx() {
    var wrap = el("div", "ocr-pv-doc");
    if (window.marked && lastMarkdown) {
      var tmp = el("div", "markdown-body");
      tmp.innerHTML = marked.parse(lastMarkdown);
      while (tmp.firstChild) wrap.appendChild(tmp.firstChild);
      return wrap;
    }
    var pages = (lastData && lastData.pages) || [];
    var found = false;
    pages.forEach(function (page) {
      (page.blocks || []).forEach(function (b) {
        if (b.type === "table" && b.html) {
          wrap.appendChild(tableFromHtml(b.html));
          found = true;
        } else {
          wrap.appendChild(el("p", null, b.text || ""));
          found = true;
        }
      });
    });
    if (!found) return emptyNote(wrap);
    return wrap;
  }

  function renderXlsx() {
    var wrap = el("div");
    var tables = [];
    ((lastData && lastData.pages) || []).forEach(function (page) {
      (page.blocks || []).forEach(function (b) {
        if (b.type === "table" && b.html) tables.push(b);
      });
    });
    if (tables.length) {
      tables.forEach(function (b, idx) {
        if (tables.length > 1) wrap.appendChild(el("h4", null, "表格 " + (idx + 1)));
        wrap.appendChild(tableFromHtml(b.html));
      });
      return wrap;
    }
    if (lastText) {
      var table = el("table", "ocr-pv-table");
      lastText.split("\n").forEach(function (line) {
        var tr = el("tr");
        tr.appendChild(el("td", null, line));
        table.appendChild(tr);
      });
      wrap.appendChild(table);
      return wrap;
    }
    return emptyNote(wrap);
  }

  function renderJson() {
    var wrap = el("div");
    wrap.appendChild(el("pre", "ocr-pv-pre", JSON.stringify(lastData || {}, null, 2)));
    return wrap;
  }

  function renderPdf() {
    var wrap = el("div");
    wrap.appendChild(el("p", null, "双层 PDF：原图叠加不可见文字层，请通过下方导出下载查看。"));
    if (lastText) wrap.appendChild(el("pre", "ocr-pv-pre", lastText));
    return wrap;
  }

  var RENDERERS = { txt: renderTxt, docx: renderDocx, xlsx: renderXlsx, pdf: renderPdf, json: renderJson };

  function selectPreviewTab(active) {
    Array.prototype.forEach.call(tabsEl.querySelectorAll(".ocr-pv-tab"), function (t) {
      t.className = "ocr-pv-tab";
    });
    active.className = "ocr-pv-tab on";
    bodyEl.textContent = "";
    bodyEl.appendChild((RENDERERS[active.getAttribute("data-fmt")] || renderTxt)());
  }

  function openPreview() {
    if (!lastData) return;
    var fmts = selectedFormats();
    tabsEl.textContent = "";
    bodyEl.textContent = "";
    subEl.textContent = fmts.map(function (f) { return FMT_NAMES[f] || f; }).join(" / ");
    fmts.forEach(function (fmt, idx) {
      var tab = el("button", "ocr-pv-tab" + (idx === 0 ? " on" : ""), FMT_NAMES[fmt] || fmt);
      tab.type = "button";
      tab.setAttribute("data-fmt", fmt);
      tab.addEventListener("click", function () { selectPreviewTab(tab); });
      tabsEl.appendChild(tab);
    });
    bodyEl.appendChild((RENDERERS[fmts[0]] || renderTxt)());
    maskEl.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closePreview() {
    maskEl.hidden = true;
    document.body.style.overflow = "";
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

  function tickProgress() {
    var sec = Math.floor((Date.now() - startAt) / 1000);
    var pct = Math.min(90, 15 + sec * 0.15);
    progressFill.style.width = pct + "%";
    if (sec < 30) {
      setStatus("正在加载识别模型并排队... " + sec + "s", "");
    } else if (sec < 180) {
      setStatus("正在识别文字与版面，扫描件约需数分钟... " + sec + "s", "");
    } else {
      setStatus("表格结构识别中，请继续等待... " + sec + "s", "");
    }
  }

  function finishUI() {
    if (tickTimer) clearInterval(tickTimer);
    btn.disabled = false;
    btn.textContent = "开始识别";
    setTimeout(function () {
      progressEl.className = "ocr-progress";
      progressFill.style.width = "0";
    }, 800);
  }

  function submit() {
    if (srcMode === "file") {
      if (!selectedFile) {
        setStatus("请先选择图片或 PDF 文件", "error");
        return;
      }
    } else {
      setStatus("离线模式暂不支持链接输入，请选择本地文件", "error");
      return;
    }

    hideResult();
    btn.disabled = true;
    btn.textContent = "识别中...";
    progressEl.className = "ocr-progress visible";
    progressFill.style.width = "15%";
    startAt = Date.now();
    tickTimer = setInterval(tickProgress, 1000);
    setStatus("正在识别，请稍候...", "");

    var form = new FormData();
    form.append("file", selectedFile);
    form.append("ocr_model", selectedOcrModel());

    fetch("/api/ocr", { method: "POST", body: form })
      .then(function (resp) {
        return resp.text().then(function (body) {
          var data; try { data = JSON.parse(body); } catch (_) { data = {}; }
          if (!resp.ok) throw new Error(data.detail || "识别失败（HTTP " + resp.status + "）");
          pollOcr(data.task_id);
        });
      })
      .catch(function (err) {
        setStatus((err && err.message) ? err.message : "识别失败", "error");
        finishUI();
      });
  }

  function pollOcr(taskId) {
    fetch("/api/ocr/" + encodeURIComponent(taskId))
      .then(function (resp) {
        return resp.text().then(function (body) {
          var data; try { data = JSON.parse(body); } catch (_) { data = {}; }
          if (!resp.ok) throw new Error(data.detail || "查询失败（HTTP " + resp.status + "）");
          return data;
        });
      })
      .then(function (data) {
        // done 响应：无 state 字段且含 text（后端直接返回 result dict）
        if (data.text !== undefined) {
          progressFill.style.width = "100%";
          showResult(data);
          setStatus(data.text ? "识别完成" : "识别完成，但未找到文字", "success");
          resultEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
          finishUI();
        } else if (data.state === "error") {
          setStatus(data.detail || "识别失败", "error");
          finishUI();
        } else {
          var _m = selectedOcrModel();
          setStatus("正在识别，请稍候...（" + (_m === "medium" ? "medium 模型" : "small 模型") + "约需数分钟）", "");
          setTimeout(function () { pollOcr(taskId); }, 3000);
        }
      })
      .catch(function (err) {
        setStatus((err && err.message) ? err.message : "识别失败", "error");
        finishUI();
      });
  }

  tabFile.addEventListener("click", function () { setSrcMode("file"); });
  tabUrl.addEventListener("click", function () { setSrcMode("url"); });

  dropZone.addEventListener("click", function () { fileInput.click(); });
  fileInput.addEventListener("change", function (e) {
    if (e.target.files && e.target.files[0]) showFile(e.target.files[0]);
  });
  fileRemove.addEventListener("click", function (e) {
    e.stopPropagation();
    clearFile();
  });

  ["dragenter", "dragover"].forEach(function (evt) {
    dropZone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropZone.classList.add("drag-over");
    });
  });
  ["dragleave", "drop"].forEach(function (evt) {
    dropZone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropZone.classList.remove("drag-over");
    });
  });
  dropZone.addEventListener("drop", function (e) {
    if (e.dataTransfer.files && e.dataTransfer.files[0]) showFile(e.dataTransfer.files[0]);
  });

  fmtBoxes.forEach(function (box) {
    box.addEventListener("change", function () {
      box.closest(".ocr-chip").className = "ocr-chip" + (box.checked ? " on" : "");
    });
  });

  var modelHints = {
    medium: "模糊字迹识别率更高，适合考试卷/低清扫描；约 4–6 分钟/页，大文件内存压力较大（2 核 CPU）。",
    small: "资源占用低、稳定不卡死，适合日常识别；约 3–4 分钟/页（2 核 CPU）。",
  };
  var modelEls = Array.prototype.slice.call(document.querySelectorAll(".ocr-model"));
  var modelHintEl = document.getElementById("ocr-model-hint");
  function selectedOcrModel() {
    var on = document.querySelector(".ocr-model.on");
    return on ? on.getAttribute("data-model") : "small";
  }
  modelEls.forEach(function (m) {
    m.addEventListener("click", function () {
      modelEls.forEach(function (x) { x.classList.remove("on"); });
      m.classList.add("on");
      if (modelHintEl) modelHintEl.textContent = modelHints[m.getAttribute("data-model")] || "";
    });
  });

  btn.addEventListener("click", submit);
  resetBtn.addEventListener("click", function () {
    clearFile();
    urlInput.value = "";
    hideResult();
    setStatus("", "");
  });
  copyBtn.addEventListener("click", function () { copyText(lastText, copyBtn); });
  copyAllBtn.addEventListener("click", function () { copyText(lastText, copyAllBtn); });
  previewBtn.addEventListener("click", openPreview);
  previewCloseBtn.addEventListener("click", closePreview);
  maskEl.addEventListener("click", function (e) { if (e.target === maskEl) closePreview(); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !maskEl.hidden) closePreview();
  });
})();
