document.addEventListener('DOMContentLoaded', function() {
  const form = document.getElementById('tailor-form');
  const apiKeyInput = document.getElementById('api-key');
  const resumeFileInput = document.getElementById('resume-file');
  const jdTextInput = document.getElementById('jd-text');
  const statusDiv = document.getElementById('status');
  const submitButton = document.getElementById('submit-button');

  // 1. Load saved API key and get Job Description from page
  // ==========================================================
  
  // Load API key from storage
  chrome.storage.local.get(['apiKey'], function(result) {
    if (result.apiKey) {
      apiKeyInput.value = result.apiKey;
    }
  });

  // Get active tab to message the content script
  chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
    chrome.scripting.executeScript({
      target: { tabId: tabs[0].id },
      files: ['content.js']
    }, () => {
      chrome.tabs.sendMessage(tabs[0].id, { message: "get_jd" }, function(response) {
        if (chrome.runtime.lastError) {
          // Handle error, e.g., content script not injected
          console.log(chrome.runtime.lastError.message);
          jdTextInput.placeholder = "Could not automatically get Job Description from this page.";
          return;
        }
        if (response && response.jd) {
          jdTextInput.value = response.jd;
        }
      });
    });
  });

  // 2. Handle Form Submission
  // ==========================================================
  form.addEventListener('submit', function(event) {
    event.preventDefault();

    const apiKey = apiKeyInput.value.trim();
    const resumeFile = resumeFileInput.files[0];
    const jdText = jdTextInput.value.trim();

    if (!apiKey || !resumeFile || !jdText) {
      statusDiv.textContent = 'Please fill in all fields.';
      statusDiv.style.color = 'red';
      return;
    }

    // Save the API key for next time
    chrome.storage.local.set({ apiKey: apiKey });

    // 3. Call the Backend API
    // ==========================================================
    const formData = new FormData();
    formData.append('api_key', apiKey);
    formData.append('jd_text', jdText);
    formData.append('resume_file', resumeFile);

    statusDiv.textContent = 'Processing... This may take a moment.';
    statusDiv.style.color = 'black';
    submitButton.disabled = true;

    fetch('http://127.0.0.1:8000/tailor/', {
      method: 'POST',
      body: formData,
    })
    .then(response => {
      if (response.ok) {
        return response.blob(); // Expecting a PDF file as a blob
      } else {
        // If the server returns an error, get the error message
        return response.json().then(errorData => {
          throw new Error(errorData.detail || 'An unknown error occurred.');
        });
      }
    })
    .then(blob => {
      // 4. Handle Success (PDF Download)
      // ==========================================================
      statusDiv.textContent = 'Success! Your resume is downloading.';
      statusDiv.style.color = 'green';
      submitButton.disabled = false;

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = 'Optimized_Resume.pdf';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    })
    .catch(error => {
      // 5. Handle Error
      // ==========================================================
      console.error('Error:', error);
      statusDiv.textContent = `Error: ${error.message}`;
      statusDiv.style.color = 'red';
      submitButton.disabled = false;
    });
  });
});
