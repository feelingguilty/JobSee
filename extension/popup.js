document.addEventListener('DOMContentLoaded', function() {
  // UI Elements
  const setupView = document.getElementById('setup-view');
  const analyzingView = document.getElementById('analyzing-view');
  const insightsView = document.getElementById('insights-view');
  const statusText = document.getElementById('status-text');
  const analysisContent = document.getElementById('analysis-content');
  const errorBar = document.getElementById('error-bar');
  const errorText = document.getElementById('error-text');

  const form = document.getElementById('tailor-form');
  const apiKeyInput = document.getElementById('api-key');
  const resumeFileInput = document.getElementById('resume-file');
  const fileDropCard = document.getElementById('file-drop-card');
  const resumeStatus = document.getElementById('resume-status');
  const jdTextInput = document.getElementById('jd-text');
  const submitButton = document.getElementById('submit-button');
  const downloadButton = document.getElementById('download-button');
  const restartButton = document.getElementById('restart-button');

  let savedResumeBlob = null;
  let lastApiResponse = null;

  // View Controller
  function showView(viewId) {
    [setupView, analyzingView, insightsView].forEach(v => v.classList.remove('active'));
    document.getElementById(viewId).classList.add('active');
    errorBar.style.display = 'none';
  }

  function showError(msg) {
    errorBar.style.display = 'flex';
    errorText.textContent = msg;
    showView('setup-view');
  }

  // File Upload Handling
  fileDropCard.addEventListener('click', () => resumeFileInput.click());
  resumeFileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      const file = e.target.files[0];
      updateResumeStatus(file.name);
      savedResumeBlob = null; // User manually uploaded, clear blob reference
    }
  });

  function updateResumeStatus(name) {
    fileDropCard.innerHTML = `<span>File: <strong>${name}</strong></span><p style="font-size:0.75rem">Click to change</p>`;
    fileDropCard.style.borderColor = 'var(--success)';
  }

  // Helper: Convert File to Base64
  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result);
      reader.onerror = error => reject(error);
    });
  }

  // Helper: Convert Base64 (Data URL) to Blob
  async function base64ToBlob(base64) {
    const res = await fetch(base64);
    return await res.blob();
  }

  // 1. Initial Load
  chrome.storage.local.get(['apiKey', 'savedResume'], async function(result) {
    if (result.apiKey) apiKeyInput.value = result.apiKey;

    if (result.savedResume) {
      try {
        savedResumeBlob = await base64ToBlob(result.savedResume);
        updateResumeStatus("Saved PDF Resume");
        detectJD();
      } catch (e) {
        console.error("Error loading saved resume:", e);
        chrome.storage.local.remove('savedResume');
      }
    } else {
      detectJD();
    }
  });

  function detectJD() {
    chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
      if (!tabs[0]) return;
      chrome.scripting.executeScript({
        target: { tabId: tabs[0].id },
        files: ['content.js']
      }, () => {
        chrome.tabs.sendMessage(tabs[0].id, { message: "get_jd" }, function(response) {
          if (!chrome.runtime.lastError && response && response.jd) {
            jdTextInput.value = response.jd;
          }
        });
      });
    });
  }

  // 2. Submit Handler
  form.addEventListener('submit', async function(e) {
    e.preventDefault();
    const apiKey = apiKeyInput.value.trim();
    const jdText = jdTextInput.value.trim();
    let resumeFile = savedResumeBlob;

    if (resumeFileInput.files.length > 0) {
      resumeFile = resumeFileInput.files[0];
    }

    if (!apiKey || !resumeFile || !jdText) {
      showError("Please fill in all requirements.");
      return;
    }

    showView('analyzing-view');
    statusText.textContent = "Step 1/3: Extracting Resume Text...";

    // Save Data
    chrome.storage.local.set({ apiKey: apiKey });
    if (resumeFileInput.files.length > 0) {
      const b64 = await fileToBase64(resumeFileInput.files[0]);
      chrome.storage.local.set({ savedResume: b64 });
    }

    // Call API
    const formData = new FormData();
    formData.append('api_key', apiKey);
    formData.append('jd_text', jdText);
    formData.append('resume_file', resumeFile, "resume.pdf");

    setTimeout(() => { statusText.textContent = "Step 2/3: AI is analyzing gaps..."; }, 2000);
    setTimeout(() => { statusText.textContent = "Step 3/3: Re-writing and Compiling PDF..."; }, 10000);

    try {
      const response = await fetch('http://127.0.0.1:8000/tailor/', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        let errorMsg = "API Failure";
        try {
            const errData = await response.json();
            errorMsg = errData.detail || errData.message || JSON.stringify(errData);
        } catch (e) {
            errorMsg = `Server Error (${response.status})`;
        }
        throw new Error(errorMsg);
      }

      const data = await response.json();
      lastApiResponse = data;

      // Render Insights
      analysisContent.innerHTML = formatAnalysis(data.analysis);
      showView('insights-view');

    } catch (err) {
      showError(err.message);
    }
  });

  function formatAnalysis(text) {
    // Simple markdown-ish formatting for keywords and bolding
    return text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
               .replace(/\* (.*?)\n/g, '<span class="badge">$1</span> ')
               .replace(/\n/g, '<br>');
  }

  // 3. Action Handlers
  downloadButton.addEventListener('click', () => {
    if (!lastApiResponse || !lastApiResponse.pdf_base64) return;
    
    const base64Data = lastApiResponse.pdf_base64;
    const binData = atob(base64Data);
    const arr = new Uint8Array(binData.length);
    for (let i = 0; i < binData.length; i++) arr[i] = binData.charCodeAt(i);
    
    const blob = new Blob([arr], { type: 'application/pdf' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = lastApiResponse.filename || 'Optimized_Resume.pdf';
    a.click();
    URL.revokeObjectURL(url);
  });

  restartButton.addEventListener('click', () => showView('setup-view'));
});
