"use strict";
try {
  const saved = localStorage.getItem("mt-theme");
  if (saved === "light" || saved === "dark") document.documentElement.setAttribute("data-theme", saved);
} catch (error) {  }
