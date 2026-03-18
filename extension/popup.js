document.addEventListener('DOMContentLoaded', function() {
  const form = document.getElementById('tailor-form');
  const apiKeyInput = document.getElementById('api-key');
  const resumeFileInput = document.getElementById('resume-file');
  const jdTextInput = document.getElementById('jd-text');
  const statusDiv = document.getElementById('status');
  const submitButton = document.getElementById('submit-button');
  const savedResumeInfo = document.getElementById('saved-resume-info');
  const clearResumeLink = document.getElementById('clear-resume');

  let savedResumeBlob = null; // Will hold the Blob if loaded from storage
  let isAutoRunning = false;

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

  // 1. Load Saved Data & Initialize
  // ==========================================================
  chrome.storage.local.get(['apiKey', 'savedResume'], async function(result) {
    if (result.apiKey) {
      apiKeyInput.value = result.apiKey;
    }

    if (result.savedResume) {
      try {
        savedResumeBlob = await base64ToBlob(result.savedResume);
        // Update UI to show saved resume state
        resumeFileInput.style.display = 'none';
        savedResumeInfo.style.display = 'block';
        resumeFileInput.removeAttribute('required'); // Not required if we have one
        
        // If we have API key and Resume, try to auto-run
        if (result.apiKey) {
            detectJDAndAutoRun();
        } else {
            detectJDOnly(); // Just get JD, don't run
        }
      } catch (e) {
        console.error("Error loading saved resume:", e);
        chrome.storage.local.remove('savedResume'); // Clear corrupted data
      }
    } else {
        detectJDOnly();
    }
  });

  // Clear Saved Resume Handler
  clearResumeLink.addEventListener('click', function(e) {
    e.preventDefault();
    chrome.storage.local.remove('savedResume', function() {
      savedResumeBlob = null;
      resumeFileInput.style.display = 'block';
      savedResumeInfo.style.display = 'none';
      resumeFileInput.value = ''; // Clear file input
      resumeFileInput.setAttribute('required', 'true');
      statusDiv.textContent = "Saved resume cleared.";
      statusDiv.style.color = "blue";
    });
  });

  // Function to detect JD only (no auto-run)
  function detectJDOnly() {
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

  // Function to detect JD and Auto-Run
  function detectJDAndAutoRun() {
    statusDiv.textContent = "Auto-detecting JD...";
    statusDiv.style.color = "blue";

    chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
      if (!tabs[0]) return;

      chrome.scripting.executeScript({
        target: { tabId: tabs[0].id },
        files: ['content.js']
      }, () => {
        chrome.tabs.sendMessage(tabs[0].id, { message: "get_jd" }, function(response) {
          if (chrome.runtime.lastError) {
            console.log(chrome.runtime.lastError.message);
            statusDiv.textContent = "Could not access page content.";
            return;
          }

          if (response && response.jd && response.jd.trim().length > 50) {
            jdTextInput.value = response.jd;
            statusDiv.textContent = "JD Detected! Auto-generating resume...";
            statusDiv.style.color = "blue";
            isAutoRunning = true;
            submitForm(); // Trigger submission automatically
          } else {
            statusDiv.textContent = "Could not detect a valid JD automatically.";
            statusDiv.style.color = "orange";
          }
        });
      });
    });
  }


  // 2. Handle Form Submission
  // ==========================================================
  function submitForm() {
    const apiKey = apiKeyInput.value.trim();
    const jdText = jdTextInput.value.trim();
    let resumeFile = null;

    if (savedResumeBlob) {
        resumeFile = savedResumeBlob;
    } else if (resumeFileInput.files.length > 0) {
        resumeFile = resumeFileInput.files[0];
    }

    if (!apiKey || !resumeFile || !jdText) {
      statusDiv.textContent = 'Please fill in all fields (API Key, Resume, JD).';
      statusDiv.style.color = 'red';
      return;
    }

    // Save API key
    chrome.storage.local.set({ apiKey: apiKey });

    // Save Resume if it was a new upload
    if (!savedResumeBlob && resumeFileInput.files.length > 0) {
        fileToBase64(resumeFileInput.files[0]).then(base64 => {
            chrome.storage.local.set({ savedResume: base64 });
        }).catch(err => console.error("Error saving resume:", err));
    }

    // 3. Call the Backend API
    // ==========================================================
    const formData = new FormData();
    formData.append('api_key', apiKey);
    formData.append('jd_text', jdText);
    // Append the file (Blob or File object) with a filename
    formData.append('resume_file', resumeFile, "resume.pdf"); 

    statusDiv.textContent = 'Processing... This may take a moment.';
    statusDiv.style.color = 'black';
    submitButton.disabled = true;

    fetch('http://127.0.0.1:8000/tailor/', {
      method: 'POST',
      body: formData,
    })
    .then(response => {
      if (response.ok) {
        return response.blob(); 
      } else {
        return response.json().then(errorData => {
          throw new Error(errorData.detail || 'An unknown error occurred.');
        });
      }
    })
    .then(blob => {
      // 4. Handle Success
      statusDiv.textContent = 'Success! Your resume is downloading.';
      statusDiv.style.color = 'green';
      submitButton.disabled = false;

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = 'Optimized_Resume.docx'; // Update extension
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    })
    .catch(error => {
      console.error('Error:', error);
      statusDiv.textContent = `Error: ${error.message}`;
      statusDiv.style.color = 'red';
      submitButton.disabled = false;
    });
  }

  form.addEventListener('submit', function(event) {
    event.preventDefault();
    submitForm();
  });
});
