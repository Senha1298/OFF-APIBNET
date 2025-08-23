function startCountdownToMidnight(display) {
    function updateCountdown() {
        const now = new Date();
        const midnight = new Date();
        midnight.setHours(24, 0, 0, 0); // Next midnight
        
        const timeDiff = midnight.getTime() - now.getTime();
        
        if (timeDiff <= 0) {
            display.textContent = "Tempo restante: 00h 00m 00s";
            return;
        }
        
        const hours = Math.floor(timeDiff / (1000 * 60 * 60));
        const minutes = Math.floor((timeDiff % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((timeDiff % (1000 * 60)) / 1000);
        
        const hoursStr = hours < 10 ? "0" + hours : hours;
        const minutesStr = minutes < 10 ? "0" + minutes : minutes;
        const secondsStr = seconds < 10 ? "0" + seconds : seconds;
        
        display.textContent = `Tempo restante: ${hoursStr}h ${minutesStr}m ${secondsStr}s`;
    }
    
    updateCountdown(); // Update immediately
    setInterval(updateCountdown, 1000); // Update every second
}

function getNextDay() {
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.getDate().toString().padStart(2, '0');
}

window.onload = function () {
    const countdownElement = document.getElementById('countdown');
    if (countdownElement) {
        startCountdownToMidnight(countdownElement);
    }

    // Removido o texto das regras do Pix para mostrar apenas o formulário de consulta
};