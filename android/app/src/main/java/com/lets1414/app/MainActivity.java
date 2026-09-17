package com.lets1414.app;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
  @Override public void onCreate(android.os.Bundle savedInstanceState) {
    registerPlugin(PrinterPlugin.class);
    super.onCreate(savedInstanceState);
  }

  // 화면을 꺼도 유튜브·녹음 소리는 계속 나야 한다.
  // Capacitor 는 앱이 뒤로 가면 WebView 를 재우는데, 그러면 소리도 같이 끊긴다.
  // 다시 깨워 두면 소리만 이어진다 (화면은 어차피 안 보인다).
  @Override public void onPause() {
    super.onPause();
    if (bridge != null && bridge.getWebView() != null) {
      bridge.getWebView().onResume();
      bridge.getWebView().resumeTimers();
    }
  }
}
