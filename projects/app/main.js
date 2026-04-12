"use strict";

const signupForm = document.getElementById("signupForm");
const emailInput = document.getElementById("emailInput");
const submitBtn = document.getElementById("submitBtn");
const formError = document.getElementById("formError");
const successPanel = document.getElementById("successPanel");
const primaryCtas = Array.from(document.querySelectorAll(".primary-cta"));
const plansSection = document.getElementById("plans");
const planToggles = Array.from(document.querySelectorAll(".plan-toggle"));
const planDetailButtons = Array.from(document.querySelectorAll(".plan-detail-btn"));
const planCards = Array.from(document.querySelectorAll("[data-plan-card]"));
const planPanelKicker = document.getElementById("planPanelKicker");
const planPanelTitle = document.getElementById("planPanelTitle");
const planPanelCopy = document.getElementById("planPanelCopy");
const planPanelList = document.getElementById("planPanelList");

const SIGNUP_ENDPOINT = "";
const ANALYTICS_KEY = "__dayflowLandingEvents";
const LEAD_STORAGE_KEY = "__dayflowLandingLeads";

const PLAN_CONTENT = {
  free: {
    kicker: "Free plan",
    title: "Keep your everyday plan frictionless.",
    copy: "Start with the essentials and get a clean view of tasks, reminders, and calendar blocks without paying upfront.",
    points: [
      "One home for tasks, reminders, and time blocks",
      "Easy entry for students, freelancers, and creators",
      "Clear upgrade path when your schedule gets more demanding",
    ],
  },
  pro: {
    kicker: "Pro plan",
    title: "Upgrade when you want stronger planning support.",
    copy: "Pro is for people who need richer planning views, smarter nudges, and a more complete way to manage a busy week.",
    points: [
      "More complete visibility into your day and week",
      "Smarter routine support when plans shift",
      "Clear value at $12/month or $96/year for heavier schedules",
    ],
  },
};

let signupSubmitting = false;
let plansViewed = false;
let activePlanId = "free";

function readStorage(key) {
  try {
    return JSON.parse(window.localStorage.getItem(key) || "[]");
  } catch {
    return [];
  }
}

function writeStorage(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    return;
  }
}

function setFormError(message) {
  formError.textContent = message || "";
}

function setSubmittingState(isSubmitting) {
  signupSubmitting = isSubmitting;
  submitBtn.disabled = isSubmitting;
  submitBtn.textContent = isSubmitting ? "Creating..." : "Create Free Account";
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

function trackEvent(eventName, payload = {}) {
  const event = {
    event: eventName,
    payload,
    at: new Date().toISOString(),
  };
  const existing = readStorage(ANALYTICS_KEY);
  existing.push(event);
  writeStorage(ANALYTICS_KEY, existing);

  if (typeof window.console !== "undefined" && typeof window.console.info === "function") {
    window.console.info("[analytics]", event);
  }
}

function persistLeadLocally(email) {
  const existing = readStorage(LEAD_STORAGE_KEY);
  existing.push({ email, at: new Date().toISOString() });
  writeStorage(LEAD_STORAGE_KEY, existing);
}

async function submitLead(email) {
  if (SIGNUP_ENDPOINT) {
    const response = await fetch(SIGNUP_ENDPOINT, {
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

function handleSignupSuccess(email) {
  signupForm.hidden = true;
  successPanel.hidden = false;
  trackEvent("signup_submit_success", {
    emailDomain: email.split("@")[1] || "",
  });
}

function renderPlanPanel(planId) {
  const plan = PLAN_CONTENT[planId];
  if (!plan) {
    return;
  }

  activePlanId = planId;
  planPanelKicker.textContent = plan.kicker;
  planPanelTitle.textContent = plan.title;
  planPanelCopy.textContent = plan.copy;
  planPanelList.innerHTML = "";

  for (const point of plan.points) {
    const item = document.createElement("li");
    item.textContent = point;
    planPanelList.appendChild(item);
  }

  for (const toggle of planToggles) {
    const isActive = toggle.dataset.planTarget === planId;
    toggle.classList.toggle("is-active", isActive);
    toggle.setAttribute("aria-selected", isActive ? "true" : "false");
  }

  for (const card of planCards) {
    card.classList.toggle("is-active", card.dataset.planCard === planId);
  }
}

function setActivePlan(planId, source) {
  if (!PLAN_CONTENT[planId]) {
    return;
  }
  renderPlanPanel(planId);
  trackEvent("plan_interest_click", { plan: planId, source });
}

function trackPlansViewOnce() {
  if (plansViewed) {
    return;
  }
  plansViewed = true;
  trackEvent("plan_section_view", { activePlan: activePlanId });
}

function bindPlanViewTracking() {
  if (!plansSection) {
    return;
  }
  if (typeof window.IntersectionObserver !== "function") {
    trackPlansViewOnce();
    return;
  }

  const observer = new window.IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          trackPlansViewOnce();
          observer.disconnect();
          break;
        }
      }
    },
    { threshold: 0.35 }
  );
  observer.observe(plansSection);
}

async function handleSubmit(event) {
  event.preventDefault();
  if (signupSubmitting) {
    return;
  }

  const email = emailInput.value.trim().toLowerCase();
  const validationMessage = getEmailValidationMessage(email);
  if (validationMessage) {
    setFormError(validationMessage);
    emailInput.focus();
    return;
  }

  setFormError("");
  setSubmittingState(true);

  try {
    await submitLead(email);
    handleSignupSuccess(email);
  } catch {
    setFormError("Signup failed. Please try again.");
  } finally {
    setSubmittingState(false);
  }
}

function prefillRecentEmail() {
  const leads = readStorage(LEAD_STORAGE_KEY);
  if (leads.length === 0) {
    return;
  }

  const latestLead = leads[leads.length - 1];
  if (latestLead && latestLead.email) {
    emailInput.value = String(latestLead.email);
  }
}

signupForm.addEventListener("submit", handleSubmit);
emailInput.addEventListener("input", () => {
  if (formError.textContent) {
    setFormError(getEmailValidationMessage(emailInput.value));
  }
});

for (const cta of primaryCtas) {
  cta.addEventListener("click", () => {
    trackEvent("primary_cta_click", {
      location: cta.dataset.ctaLocation || "unknown",
    });
  });
}

for (const toggle of planToggles) {
  toggle.addEventListener("click", () => {
    setActivePlan(toggle.dataset.planTarget || "free", "tab");
  });
}

for (const button of planDetailButtons) {
  button.addEventListener("click", () => {
    setActivePlan(button.dataset.planFocus || "free", "detail_button");
  });
}

renderPlanPanel("free");
bindPlanViewTracking();
prefillRecentEmail();
trackEvent("page_view", { page: "dayflow_consumer_landing" });
