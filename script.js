const BACKEND_API = 'https://geoflow.onrender.com';
const messagesEl = document.getElementById('messages');
const form = document.getElementById('chat-form');
const input = document.getElementById('msg');
const welcomeCard = document.querySelector('.welcome-card');

let messageCount = 0;
let selectedLanguage = 'en';
let awaitingLocationConfirmation = false;
let detectedLocation = null;

// Event listeners for the language buttons
const langButtons = document.querySelectorAll('.lang-button');
langButtons.forEach(button => {
    button.addEventListener('click', () => {
        // Remove 'active' class from all buttons
        langButtons.forEach(btn => btn.classList.remove('active'));
        // Add 'active' class to the clicked button
        button.classList.add('active');
        // Update the selected language
        selectedLanguage = button.dataset.lang;
    });
});

function addMessage(text, who='bot', isHtml=false){
    const d = document.createElement('div');
    d.className = 'msg ' + (who === 'user' ? 'user' : 'bot');
    if (isHtml) {
        d.innerHTML = text;
    } else {
        d.innerHTML = text.replace(/\n/g, '<br>');
    }
    messagesEl.appendChild(d);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

const createDownloadButton = (location) => {
    const button = document.createElement('button');
    button.className = 'download-button';
    button.textContent = `Download Excel Report for ${location}`;
    button.onclick = () => {
        window.open(`${BACKEND_API}/report/${location}`, '_blank');
    };
    return button;
};


form.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const message = input.value.trim();
    if(!message) return;

    if (welcomeCard) {
        welcomeCard.remove();
    }

    addMessage(message, 'user');
    input.value = '';
    messageCount++;
    
    // Check if the user is confirming the detected location
    if (awaitingLocationConfirmation) {
        const userConfirmation = message.toLowerCase().trim();
        if (userConfirmation === 'yes' || userConfirmation === 'y' || userConfirmation === 'proceed') {
            awaitingLocationConfirmation = false;
            fetchGroundwaterDataForLocation(detectedLocation);
        } else {
            awaitingLocationConfirmation = false;
            addMessage("No problem. Please type your city or a landmark to get groundwater information.");
        }
        return;
    }

    try{
        const res = await fetch(`${BACKEND_API}/query`, {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({
                message,
                language: selectedLanguage
            })
        });
        const data = await res.json();
        
        addMessage(data.reply || JSON.stringify(data));
        
        if (data.location) {
            const downloadContainer = document.createElement('div');
            downloadContainer.className = 'download-container';
            downloadContainer.appendChild(createDownloadButton(data.location));
            messagesEl.appendChild(downloadContainer);
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }
    }catch(err){
        addMessage('Error contacting backend: '+ err.message);
    }
});

// --- GEOLOCATION CODE ---
// New function to handle fetching the data
async function fetchGroundwaterDataForLocation(position) {
    if (welcomeCard) {
        welcomeCard.remove();
    }
    
    const { latitude, longitude } = position.coords;
    addMessage("Fetching the latest groundwater levels for your area...");
    
    try {
        const res = await fetch(`${BACKEND_API}/query_by_location`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                latitude,
                longitude,
                language: selectedLanguage
            })
        });
        const data = await res.json();
        
        addMessage(data.reply || JSON.stringify(data));
        
        if (data.location) {
            const downloadContainer = document.createElement('div');
            downloadContainer.className = 'download-container';
            downloadContainer.appendChild(createDownloadButton(data.location));
            messagesEl.appendChild(downloadContainer);
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }
    } catch (err) {
        addMessage('Error contacting backend with location data: ' + err.message);
    }
}

function handleGeolocationSuccess(position) {
    if (welcomeCard) {
        welcomeCard.remove(); // Remove the welcome card once we have a response
    }
    
    // Store the detected location for confirmation
    detectedLocation = position;

    // Await user confirmation
    awaitingLocationConfirmation = true;
    addMessage("I've detected your location. Would you like to proceed with this location? (Yes/No)");
}

function handleGeolocationError(error) {
    if (welcomeCard) {
        welcomeCard.remove();
    }
    
    let errorMessage = "Sorry, I couldn't detect your location automatically.";
    if (error.code === error.PERMISSION_DENIED) {
        errorMessage += " You denied the request for your location.";
    }
    
    addMessage(errorMessage);
    addMessage("Please type your city or a landmark to get groundwater information.");
}

// Check for Geolocation API support and request location on page load
if ("geolocation" in navigator) {
    navigator.geolocation.getCurrentPosition(
        handleGeolocationSuccess, 
        handleGeolocationError,
        {
            enableHighAccuracy: true,
            timeout: 5000,
            maximumAge: 0
        }
    );
} else {
    if (welcomeCard) {
        welcomeCard.remove();
    }
    addMessage("It looks like your browser doesn't support automatic location detection. Please type your location to begin.");
}
