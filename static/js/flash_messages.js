// flash_messages.js
// Handles the display of flash messages using SweetAlert2 upon DOM load.

document.addEventListener("DOMContentLoaded", () => {
  // If flashMessages exists and is a non-empty array, show each message.
  if (Array.isArray(flashMessages) && flashMessages.length > 0) {
    flashMessages.forEach((item) => {
      const [category, message] = item;
      // Validate the icon category; default to 'info' if invalid.
      const validIcons = ["success", "error", "warning", "info", "question"];
      const icon = validIcons.includes(category) ? category : "info";
      Swal.fire({
        toast: true,
        position: "top-start", // Upper-left corner
        icon,
        title: message,
        showConfirmButton: false,
        timer: 3500,
        timerProgressBar: true,
      });
    });
  }
  
  // Mark as loaded for debugging
  window.flashMessagesLoaded = true;
  console.log('✅ flash_messages.js loaded and initialized');
});
