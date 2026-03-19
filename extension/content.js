chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.message === "get_jd") {
    // Try to find the job description container in common platforms
    const jdSelectors = [
      '.jobs-description__container', // LinkedIn
      '#jobDescriptionText',         // Indeed
      '.jobDescriptionContent',       // Glassdoor
      '.description',                 // Generic
      '[id*="job-description"]',      // ID containing job-description
      '[class*="job-description"]'    // Class containing job-description
    ];

    let jd = null;
    for (const selector of jdSelectors) {
      const el = document.querySelector(selector);
      if (el && el.innerText.trim().length > 100) {
        jd = el.innerText;
        break;
      }
    }

    // Fallback to body text or selection
    jd = jd || window.getSelection().toString() || document.body.innerText;
    
    sendResponse({ jd: jd.trim() });
  }
  return true;
});
