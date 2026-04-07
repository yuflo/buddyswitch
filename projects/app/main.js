"use strict";

const form = document.getElementById("onboardingForm");
const steps = Array.from(document.querySelectorAll(".step"));
const doneState = document.getElementById("doneState");
const restartBtn = document.getElementById("restartBtn");
const progressLabel = document.getElementById("progressLabel");
const progressTrack = document.getElementById("progressTrack");
const progressFill = document.getElementById("progressFill");
const formError = document.getElementById("formError");
const nameInput = document.getElementById("name");
const goalInput = document.getElementById("goal");
const summaryName = document.getElementById("summaryName");
const summaryGoal = document.getElementById("summaryGoal");

const TOTAL_STEPS = steps.length;
let currentStep = 0;

function setStep(stepIndex) {
  currentStep = Math.max(0, Math.min(TOTAL_STEPS - 1, stepIndex));
  steps.forEach((step, index) => {
    step.classList.toggle("is-active", index === currentStep);
  });

  const progressIndex = currentStep + 1;
  progressLabel.textContent = `Step ${progressIndex} of ${TOTAL_STEPS}`;
  progressTrack.setAttribute("aria-valuenow", String(progressIndex));
  progressFill.style.width = `${(progressIndex / TOTAL_STEPS) * 100}%`;
}

function clearError() {
  formError.textContent = "";
}

function validateProfileStep() {
  const name = nameInput.value.trim();
  const goal = goalInput.value;

  if (!name) {
    formError.textContent = "Display Name is required.";
    nameInput.focus();
    return false;
  }

  if (!goal) {
    formError.textContent = "Primary Goal is required.";
    goalInput.focus();
    return false;
  }

  clearError();
  return true;
}

function setSummary() {
  summaryName.textContent = nameInput.value.trim();
  summaryGoal.textContent = goalInput.options[goalInput.selectedIndex].text;
}

function handleNext() {
  if (currentStep === 1 && !validateProfileStep()) {
    return;
  }
  if (currentStep === 1) {
    setSummary();
  }
  setStep(currentStep + 1);
}

function handleBack() {
  clearError();
  setStep(currentStep - 1);
}

function handleFinish() {
  form.hidden = true;
  doneState.hidden = false;
}

function handleRestart() {
  form.reset();
  form.hidden = false;
  doneState.hidden = true;
  clearError();
  summaryName.textContent = "-";
  summaryGoal.textContent = "-";
  setStep(0);
}

form.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) {
    return;
  }

  const action = target.dataset.action;
  if (!action) {
    return;
  }

  event.preventDefault();

  if (action === "next") {
    handleNext();
    return;
  }

  if (action === "back") {
    handleBack();
    return;
  }

  if (action === "finish") {
    handleFinish();
  }
});

restartBtn.addEventListener("click", handleRestart);

setStep(0);
