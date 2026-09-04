const launchProtocol = window.location.protocol;

document.documentElement.dataset.launchMode =
  launchProtocol === "http:" || launchProtocol === "https:" ? "served" : "direct-file";
