function setMinuteHand() {
    const now = new Date();
    const minutes = now.getMinutes();
    const seconds = now.getSeconds();
  
    // Calculate the degrees for the minute hand
    const minutesFraction = (minutes + seconds / 60) / 60;
    const minuteDegrees = minutesFraction * 360 - 90; // Adjust by -90deg to set 12 o'clock at -90deg
  
    const minuteHand = document.querySelector('.minute-hand');
    minuteHand.style.transform = `rotate(${minuteDegrees}deg)`;
  }
  
  // Initialize and update every second
  setMinuteHand(); // Initial call
  setInterval(setMinuteHand, 1000); // Update every second