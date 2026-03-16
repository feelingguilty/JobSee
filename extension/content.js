// This script runs on the page and listens for a request from the popup.
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.message === "get_jd") {
    // A very simple heuristic to get the job description: return all visible text on the page.
    // The user can then edit it in the popup.
    // More advanced versions could look for specific DOM elements.
    const pageText = document.body.innerText;
    sendResponse({ jd: pageText });
  }
  // Return true to indicate that the response will be sent asynchronously.
  return true;
});
