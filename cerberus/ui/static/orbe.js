/**
 * CERBERUS ORBE — Logique Client & Interactions
 * ZENITH AI — Addendum 2
 */

class CerberusOrb {
  constructor() {
    this.stage = document.getElementById("stage");
    this.orbWrapper = document.getElementById("orbWrapper");
    this.statusDot = document.getElementById("statusDot");
    this.statusText = document.getElementById("statusText");
    this.speechBubble = document.getElementById("speechBubble");
    this.contextPanel = document.getElementById("contextPanel");
    this.contextTitle = document.getElementById("contextTitle");
    this.contextBody = document.getElementById("contextBody");
    this.chatInput = document.getElementById("chatInput");
    this.sendBtn = document.getElementById("sendBtn");
    this.micBtn = document.getElementById("micBtn");
    this.btnOmnipresent = document.getElementById("btnOmnipresent");

    this.mediaRecorder = null;
    this.audioChunks = [];
    this.isRecording = false;
    this.currentAudio = null;
    this.cardDismissTimer = null;

    this.initEvents();
    this.checkPendingAlerts();
  }

  setOrbState(state) {
    this.stage.className = `stage state-${state}`;
    const dotColors = {
      idle: "#38bdf8",
      listening: "#c084fc",
      thinking: "#22d3ee",
      speaking: "#34d399",
      alert: "#ef4444"
    };
    const statusLabels = {
      idle: "VEILLE ACTIVE",
      listening: "ÉCOUTE...",
      thinking: "RÉFLEXION...",
      speaking: "CERBERUS PARLE",
      alert: "ALERTE EN COURS"
    };

    if (this.statusDot) {
      this.statusDot.style.backgroundColor = dotColors[state] || "#38bdf8";
      this.statusDot.style.boxShadow = `0 0 10px ${dotColors[state] || "#38bdf8"}`;
    }
    if (this.statusText) {
      this.statusText.textContent = statusLabels[state] || "CERBERUS";
    }
  }

  showSpeech(text) {
    if (!this.speechBubble) return;
    this.speechBubble.textContent = text;
    this.speechBubble.classList.add("visible");
  }

  hideSpeech() {
    if (this.speechBubble) {
      this.speechBubble.classList.remove("visible");
    }
  }

  showContextCard(card) {
    if (!card || !card.items || card.items.length === 0) {
      this.hideContextCard();
      return;
    }

    this.contextTitle.textContent = card.title || "Informations";
    this.contextBody.innerHTML = "";

    card.items.forEach(item => {
      const div = document.createElement("div");
      div.className = "context-item";

      if (card.type === "alerts") {
        div.innerHTML = `
          <div class="item-badge ${item.niveau === 'URGENT' ? 'badge-urgent' : 'badge-standard'}">
            Alerte #${item.id} — ${item.niveau}
          </div>
          <div style="font-weight: 600; font-size: 0.88rem; color: #f1f5f9;">${item.contact}</div>
          <div class="item-desc">${item.motif}</div>
        `;
      } else if (card.type === "drafts") {
        div.innerHTML = `
          <div class="item-badge badge-draft">Brouillon #${item.id}</div>
          <div style="font-weight: 600; font-size: 0.88rem; color: #f1f5f9;">${item.destinataire}</div>
          <div style="font-size: 0.8rem; color: #94a3b8; font-style: italic;">${item.sujet}</div>
          <div class="item-desc">${item.corps}</div>
        `;
      } else {
        div.innerHTML = `<div class="item-desc">${JSON.stringify(item)}</div>`;
      }

      this.contextBody.appendChild(div);
    });

    this.contextPanel.classList.add("active");

    // Fermeture automatique après 30 secondes d'inactivité
    clearTimeout(this.cardDismissTimer);
    this.cardDismissTimer = setTimeout(() => {
      this.hideContextCard();
    }, 30000);
  }

  hideContextCard() {
    clearTimeout(this.cardDismissTimer);
    if (this.contextPanel) {
      this.contextPanel.classList.remove("active");
    }
  }

  async playAudio(url) {
    if (!url) return;
    try {
      if (this.currentAudio) {
        this.currentAudio.pause();
      }
      this.currentAudio = new Audio(url);
      this.setOrbState("speaking");

      this.currentAudio.onended = () => {
        this.setOrbState("idle");
        setTimeout(() => this.hideSpeech(), 2500);
      };

      await this.currentAudio.play();
    } catch (e) {
      console.warn("Audio autoplay restreint ou non disponible:", e);
      this.setOrbState("idle");
    }
  }

  async sendQuery(queryText) {
    const q = queryText.trim();
    if (!q) return;

    this.setOrbState("thinking");
    this.showSpeech(q);

    try {
      const resp = await fetch("/api/vox/interact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q })
      });

      if (!resp.ok) {
        throw new Error("Erreur serveur");
      }

      const data = await resp.json();

      // Gestion des actions d'interface (UI)
      if (data.ui_action === "minimize" && window.pywebview) {
        window.pywebview.api.set_mode("omnipresent");
      } else if (data.ui_action === "restore" && window.pywebview) {
        window.pywebview.api.set_mode("fullscreen");
      } else if (data.ui_action === "open_manual") {
        window.location.href = "/manual";
        return;
      } else if (data.ui_action === "dismiss_card") {
        this.hideContextCard();
      }

      // Affichage du sous-titre
      this.showSpeech(data.text);

      // Affichage éventuel de la carte contextuelle
      if (data.context_card) {
        this.showContextCard(data.context_card);
      }

      // Lecture vocale
      if (data.audio_url) {
        await this.playAudio(data.audio_url);
      } else {
        this.setOrbState("idle");
      }

    } catch (err) {
      console.error(err);
      this.showSpeech("Désolé Akim, je rencontre une difficulté pour traiter cette demande.");
      this.setOrbState("idle");
    }
  }

  async startVoiceRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.mediaRecorder = new MediaRecorder(stream);
      this.audioChunks = [];

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      this.mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(this.audioChunks, { type: "audio/webm" });
        await this.transcribeAndSend(audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };

      this.mediaRecorder.start();
      this.isRecording = true;
      this.micBtn.classList.add("recording");
      this.setOrbState("listening");
      this.showSpeech("À votre écoute, Akim...");
    } catch (err) {
      console.error("Accès microphone refusé ou non supporté :", err);
      this.showSpeech("Microphone non disponible. Vous pouvez taper au clavier.");
      this.setOrbState("idle");
    }
  }

  stopVoiceRecording() {
    if (this.mediaRecorder && this.isRecording) {
      this.mediaRecorder.stop();
      this.isRecording = false;
      this.micBtn.classList.remove("recording");
      this.setOrbState("thinking");
    }
  }

  async transcribeAndSend(blob) {
    try {
      this.showSpeech("Transcription en cours...");
      const formData = new FormData();
      formData.append("audio", blob, "voice_input.webm");

      const resp = await fetch("/api/vox/transcribe", {
        method: "POST",
        body: formData
      });

      const data = await resp.json();
      if (data.transcription && data.transcription.trim()) {
        await this.sendQuery(data.transcription);
      } else {
        this.showSpeech("Je n'ai pas capté de parole. Rapprochez-vous du micro.");
        this.setOrbState("idle");
      }
    } catch (err) {
      console.error(err);
      this.showSpeech("Erreur de transcription audio.");
      this.setOrbState("idle");
    }
  }

  async checkPendingAlerts() {
    try {
      const resp = await fetch("/api/briefing/json");
      if (resp.ok) {
        const data = await resp.json();
        const urgentCount = data.urgent_alerts ? data.urgent_alerts.length : 0;
        if (urgentCount > 0 && this.stage.className === "stage state-idle") {
          this.setOrbState("alert");
        }
      }
    } catch (e) {
      // mode silencieux
    }
  }

  initEvents() {
    // Saisie texte
    this.sendBtn.addEventListener("click", () => {
      const val = this.chatInput.value;
      if (val) {
        this.chatInput.value = "";
        this.sendQuery(val);
      }
    });

    this.chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const val = this.chatInput.value;
        if (val) {
          this.chatInput.value = "";
          this.sendQuery(val);
        }
      }
    });

    // Clic sur l'Orbe pour réveiller / écouter
    this.orbWrapper.addEventListener("click", () => {
      if (!this.isRecording) {
        this.startVoiceRecording();
      } else {
        this.stopVoiceRecording();
      }
    });

    // Bouton Microphone
    this.micBtn.addEventListener("click", () => {
      if (!this.isRecording) {
        this.startVoiceRecording();
      } else {
        this.stopVoiceRecording();
      }
    });

    // Bascule Mode Omniprésent (synchronisé avec pywebviewready)
    if (this.btnOmnipresent) {
      this.btnOmnipresent.addEventListener("click", async () => {
        if (window.pywebview && window.pywebview.api) {
          try {
            const res = await window.pywebview.api.toggle_mode();
            if (res === "not_ready") {
              this.showSpeech("Initialisation en cours... Patientez un instant.");
            }
          } catch (err) {
            console.warn("Erreur bascule Desktop :", err);
          }
        } else {
          this.sendQuery("Passe en mode omniprésent");
        }
      });
    }

    // Fermeture manuelle de carte contextuelle
    document.getElementById("contextClose")?.addEventListener("click", () => {
      this.hideContextCard();
    });
  }
}

// Initialisation au chargement de la page
document.addEventListener("DOMContentLoaded", () => {
  window.cerberusOrb = new CerberusOrb();
});
