package com.lets1414.app;

import android.content.pm.ApplicationInfo;
import android.os.Bundle;
import android.webkit.WebView;


import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
  @Override public void onCreate(Bundle savedInstanceState) {
    // 디버그 빌드에서는 크롬 devtools 로 웹뷰를 들여다볼 수 있게 한다 (chrome://inspect).
    // 웹뷰가 만들어지기 전(super.onCreate 전)에 켜야 붙는다.
    // capacitor.config.json 에 android.webContentsDebuggingEnabled 를 두지 않는다 — 두면 Capacitor 가
    // 이 뒤에 그 값으로 덮어써 출시 빌드에서도 켜진다 (남의 폰을 잠깐 꽂아 로그인 토큰을 읽을 수 있다)
    if ((getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0) WebView.setWebContentsDebuggingEnabled(true);
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
