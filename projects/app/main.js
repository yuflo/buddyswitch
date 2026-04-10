"use strict";

const form = document.getElementById("waitlistForm");
const emailInput = document.getElementById("emailInput");
const submitBtn = document.getElementById("submitBtn");
const formError = document.getElementById("formError");
const successPanel = document.getElementById("successPanel");
const heroCta = document.getElementById("heroCta");
const pricingSection = document.getElementById("pricing");
const pricingCtas = Array.from(document.querySelectorAll(".pricing-cta"));
const paywallBackdrop = document.getElementById("paywallBackdrop");
const paywallCloseBtn = document.getElementById("paywallCloseBtn");
const paywallForm = document.getElementById("paywallForm");
const paywallEmailInput = document.getElementById("paywallEmailInput");
const paywallSubmitBtn = document.getElementById("paywallSubmitBtn");
const paywallError = document.getElementById("paywallError");
const paywallSuccessPanel = document.getElementById("paywallSuccessPanel");
const selectedPlanText = document.getElementById("selectedPlanText");

const WAITLIST_ENDPOINT = "";
const PAYWALL_INTENT_ENDPOINT = "";
const ANALYTICS_KEY = "__ultraliteWaitlistEvents";
const WAITLIST_STORAGE_KEY = "__ultraliteWaitlistLeads";
const PAYWALL_STORAGE_KEY = "__ultralitePaywallIntents";
let waitlistSubmitting = false;
let paywallSubmitting = false;
let pricingViewed = false;
let selectedPlan = null;
let lastPaywallTrigger = null;

function setWaitlistError(message) {
  formError.textContent = "";
  if (message) {
    formError.textContent = message;
  }
}

function setPaywallError(message) {
  paywallError.textContent = "";
  if (message) {
    paywallError.textContent = message;
  }
}

function getEmailValidationMessage(value) {
  const email = value.trim().toLowerCase();
  const basicEmailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!email) {
    return "Email is required.";
  }
  if (!basicEmailPattern.test(email)) {
    return "Please enter a valid email address.";
  }
  return "";
}

function setWaitlistSubmittingState(isSubmitting) {
  waitlistSubmitting = isSubmitting;
  submitBtn.disabled = isSubmitting;
  submitBtn.textContent = isSubmitting ? "Submitting..." : "Join Waitlist";
}

function setPaywallSubmittingState(isSubmitting) {
  paywallSubmitting = isSubmitting;
  paywallSubmitBtn.disabled = isSubmitting;
  paywallSubmitBtn.textContent = isSubmitting ? "Submitting..." : "Reserve Spot";
}

function trackEvent(eventName, payload = {}) {
  const event = {
    event: eventName,
    payload,
    at: new Date().toISOString(),
  };
  window[ANALYTICS_KEY] = window[ANALYTICS_KEY] || [];
  window[ANALYTICS_KEY].push(event);
  if (typeof window.console !== "undefined" && typeof window.console.info === "function") {
    window.console.info("[analytics]", event);
  }
}

function persistLeadLocally(email) {
  const existing = JSON.parse(window.localStorage.getItem(WAITLIST_STORAGE_KEY) || "[]");
  existing.push({ email, at: new Date().toISOString() });
  window.localStorage.setItem(WAITLIST_STORAGE_KEY, JSON.stringify(existing));
}

function persistPaywallIntentLocally(email, planId) {
  const existing = JSON.parse(window.localStorage.getItem(PAYWALL_STORAGE_KEY) || "[]");
  existing.push({ email, planId, at: new Date().toISOString() });
  window.localStorage.setItem(PAYWALL_STORAGE_KEY, JSON.stringify(existing));
}

async function submitLead(email) {
  if (WAITLIST_ENDPOINT) {
    const response = await fetch(WAITLIST_ENDPOINT, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email }),
    });
    if (!response.ok) {
      throw new Error("endpoint_rejected");
    }
    return;
  }
  persistLeadLocally(email);
}

async function submitPaywallIntent(email, plan) {
  if (PAYWALL_INTENT_ENDPOINT) {
    const response = await fetch(PAYWALL_INTENT_ENDPOINT, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, plan }),
    });
    if (!response.ok) {
      throw new Error("endpoint_rejected");
    }
    return;
  }
  persistPaywallIntentLocally(email, plan.id);
}

function handleSuccess(email) {
  form.hidden = true;
  successPanel.hidden = false;
  trackEvent("waitlist_submit_success", { emailDomain: email.split("@")[1] || "" });
}

function prefillPaywallEmail() {
  const candidate = emailInput.value.trim().toLowerCase();
  if (!getEmailValidationMessage(candidate)) {
    paywallEmailInput.value = candidate;
    return;
  }

  const stored = JSON.parse(window.localStorage.getItem(WAITLIST_STORAGE_KEY) || "[]");
  if (stored.length > 0 && stored[stored.length - 1].email) {
    paywallEmailInput.value = String(stored[stored.length - 1].email);
  }
}

function openPaywall(plan, triggerElement) {
  selectedPlan = plan;
  lastPaywallTrigger = triggerElement;
  selectedPlanText.textContent = `${plan.name} · ${plan.price}`;
  paywallForm.hidden = false;
  paywallSuccessPanel.hidden = true;
  paywallForm.reset();
  prefillPaywallEmail();
  setPaywallError("");
  setPaywallSubmittingState(false);
  paywallBackdrop.hidden = false;
  document.body.classList.add("has-modal");
  paywallEmailInput.focus();
  trackEvent("paywall_open", { plan: plan.id });
}

function closePaywall() {
  if (paywallBackdrop.hidden) {
    return;
  }
  paywallBackdrop.hidden = true;
  document.body.classList.remove("has-modal");
  setPaywallError("");
  setPaywallSubmittingState(false);
  paywallForm.hidden = false;
  paywallSuccessPanel.hidden = true;
  if (lastPaywallTrigger instanceof HTMLElement) {
    lastPaywallTrigger.focus();
  }
}

async function handleSubmit(event) {
  event.preventDefault();
  if (waitlistSubmitting) {
    return;
  }

  const email = emailInput.value.trim().toLowerCase();
  const validationMessage = getEmailValidationMessage(email);
  if (validationMessage) {
    setWaitlistError(validationMessage);
    emailInput.focus();
    return;
  }

  setWaitlistSubmittingState(true);
  setWaitlistError("");
  try {
    await submitLead(email);
    handleSuccess(email);
  } catch {
    setWaitlistError("Submission failed. Please try again.");
  } finally {
    setWaitlistSubmittingState(false);
  }
}

async function handlePaywallSubmit(event) {
  event.preventDefault();
  if (paywallSubmitting) {
    return;
  }
  if (!selectedPlan) {
    setPaywallError("No plan selected. Please choose a plan again.");
    return;
  }

  const email = paywallEmailInput.value.trim().toLowerCase();
  const validationMessage = getEmailValidationMessage(email);
  if (validationMessage) {
    setPaywallError(validationMessage);
    paywallEmailInput.focus();
    return;
  }

  setPaywallSubmittingState(true);
  setPaywallError("");
  try {
    await submitPaywallIntent(email, selectedPlan);
    paywallForm.hidden = true;
    paywallSuccessPanel.hidden = false;
    trackEvent("paywall_submit_intent_success", {
      plan: selectedPlan.id,
      emailDomain: email.split("@")[1] || "",
    });
  } catch {
    setPaywallError("Submission failed. Please try again.");
  } finally {
    setPaywallSubmittingState(false);
  }
}

function trackPricingViewOnce() {
  if (pricingViewed) {
    return;
  }
  pricingViewed = true;
  trackEvent("pricing_view", { plans: pricingCtas.length });
}

function bindPricingViewTracking() {
  if (!pricingSection) {
    return;
  }
  if (typeof window.IntersectionObserver !== "function") {
    trackPricingViewOnce();
    return;
  }
  const observer = new window.IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          trackPricingViewOnce();
          observer.disconnect();
          break;
        }
      }
    },
    { threshold: 0.35 }
  );
  observer.observe(pricingSection);
}

form.addEventListener("submit", handleSubmit);
emailInput.addEventListener("input", () => {
  if (formError.textContent) {
    const validationMessage = getEmailValidationMessage(emailInput.value);
    setWaitlistError(validationMessage);
  }
});
heroCta.addEventListener("click", () => trackEvent("hero_cta_click"));

for (const cta of pricingCtas) {
  cta.addEventListener("click", () => {
    const plan = {
      id: cta.dataset.plan || "unknown",
      name: cta.dataset.planName || "Unknown",
      price: cta.dataset.planPrice || "N/A",
    };
    trackEvent("pricing_cta_click", { plan: plan.id });
    openPaywall(plan, cta);
  });
}

paywallForm.addEventListener("submit", handlePaywallSubmit);
paywallEmailInput.addEventListener("input", () => {
  if (paywallError.textContent) {
    const validationMessage = getEmailValidationMessage(paywallEmailInput.value);
    setPaywallError(validationMessage);
  }
});
paywallCloseBtn.addEventListener("click", closePaywall);
paywallBackdrop.addEventListener("click", (event) => {
  if (event.target === paywallBackdrop) {
    closePaywall();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !paywallBackdrop.hidden) {
    closePaywall();
  }
});

bindPricingViewTracking();
trackEvent("page_view", { page: "ultra_lite_landing_with_pricing" });
