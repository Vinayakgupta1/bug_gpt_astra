import { io } from "socket.io-client";

// ✅ Fix: Removed `/socket.io/`, because it's added automatically
const socket = io("http://localhost:8000", {
  transports: ["websocket", "polling"],
});

socket.on("connect", () => {
  console.log("✅ Connected to Socket.IO server");
});

socket.on("scan_progress", (data) => {
  console.log("📡 Scan progress:", data);
});

socket.on("scan_complete", (data) => {
  console.log("✅ Scan complete:", data);
});

socket.on("connect_error", (error) => {
  console.error("🔴 Socket.IO connection error:", error);
});

socket.on("disconnect", (reason) => {
  console.warn("⚠️ Socket.IO disconnected:", reason);
  if (reason === "io server disconnect") {
    socket.connect(); // Reconnect if the server disconnected
  }
});

export default socket;
