import type { CSSProperties } from "react";

import { AICrm } from "./AICrm";

export default function App() {
  return (
    <div style={page}>
      <AICrm />
    </div>
  );
}

const page: CSSProperties = { minHeight: "100vh", display: "flex", flexDirection: "column" };
