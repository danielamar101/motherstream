function setMinuteHand() {
    const now = new Date();
    const minutes = now.getMinutes();
    console.log("minutes")
    console.log(minutes)
  
    // Calculate the degrees for the minute hand
    const minutesFraction = minutes / 60;
    console.log("Minutes fracion:")
    console.log(minutesFraction)
  
    const minuteDegrees = minutesFraction * 360; // Adjust by -90deg to set 12 o'clock at -90deg
  
    const minuteHand = document.querySelector('.minute-hand');
    minuteHand.style.transform = `rotate(${minuteDegrees}deg)`;
  }
  
  // Initialize and update every minute
  setMinuteHand(); // Initial call
  setInterval(setMinuteHand, 60000); // Update every minute
  