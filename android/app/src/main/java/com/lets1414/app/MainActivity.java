package com.lets1414.app;

import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.res.Configuration;
import android.graphics.drawable.Drawable;
import android.os.Bundle;
import android.view.View;
import android.webkit.JsPromptResult;
import android.webkit.JsResult;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.EditText;

import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.Bridge;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebChromeClient;

public class MainActivity extends BridgeActivity {
  // 웹뷰 글자 확대(textZoom)를 마지막으로 맞춘 시스템 글자 크기
  private float fontScale = 1f;

  @Override public void onCreate(Bundle savedInstanceState) {
    // 디버그 빌드에서는 크롬 devtools 로 웹뷰를 들여다볼 수 있게 한다 (chrome://inspect).
    // 웹뷰가 만들어지기 전(super.onCreate 전)에 켜야 붙는다.
    // capacitor.config.json 에 android.webContentsDebuggingEnabled 를 두지 않는다 — 두면 Capacitor 가
    // 이 뒤에 그 값으로 덮어써 출시 빌드에서도 켜진다 (남의 폰을 잠깐 꽂아 로그인 토큰을 읽을 수 있다)
    if ((getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0) WebView.setWebContentsDebuggingEnabled(true);
    // 최근 앱 목록에서 다시 켜거나(LAUNCHED_FROM_HISTORY) 시스템이 죽였던 화면을 되살릴 때(savedInstanceState)
    // 안드로이드는 처음 켤 때의 인텐트를 그대로 다시 준다. 앱 링크로 켰던 앱이면 Capacitor 가 그 링크를
    // appUrlOpen 으로 또 보내, 한참 전에 누른 초대·콘티 링크 화면으로 다시 끌려갔다 → 되살릴 때는 링크를 떼고 그냥 연다.
    // 되살아난 뒤 새로 누른 링크는 onNewIntent 로 따로 오므로 그대로 열린다
    Intent it = getIntent();
    if (it != null && Intent.ACTION_VIEW.equals(it.getAction())
        && (savedInstanceState != null || (it.getFlags() & Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY) != 0)) {
      it.setAction(Intent.ACTION_MAIN);
      it.setData(null);
    }
    registerPlugin(PrinterPlugin.class);
    super.onCreate(savedInstanceState);
    fontScale = getResources().getConfiguration().fontScale;
    // confirm·alert·prompt 창 단추를 한국어로 (AND1-06). Capacitor 창은 "OK"·"Cancel" 을 박아 둬서 메시지는 한국어인데
    // 단추만 영어였다 (iOS 는 SceneDelegate 의 KoreanDialogs). 파일 고르기·권한 묻기는 부모(BridgeWebChromeClient) 것을 그대로 쓴다.
    // 부모가 만들며 결과 받기(registerForActivityResult)를 거는데, 그건 액티비티가 시작되기 전(onCreate)이어야 한다
    if (bridge != null && bridge.getWebView() != null) bridge.getWebView().setWebChromeClient(new KoreanDialogs(bridge));
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

  // 돌리기·다크 모드·글자 크기처럼 액티비티를 새로 만들지 않고 넘기는 바뀜(AndroidManifest configChanges).
  // Capacitor 의 SystemBars 는 이때 상태바를 켤 때 정한 스타일(시스템 테마 — 라이트면 검은 아이콘)로 되돌리고 창 바탕도
  // 테마 색으로 바꾼다. 웹이 StatusBar 로 칠한 스타일은 모른다 → 로그인·무대·다크 테마처럼 어두운 화면에서 돌리면 시계·배터리가
  // 검은색이 되어 묻혔다 (AND1-03 · AND2-08). 웹은 같은 색을 또 부르지 않으므로(barNow) 다음 화면 바뀜까지 그대로였다.
  // 바뀌기 전 모양(상태바·내비게이션 바 아이콘 색 · 창 바탕)을 기억했다가 그대로 되돌린다. 테마를 따라 바뀌어야 하면 웹이 곧 다시 칠한다
  @Override public void onConfigurationChanged(Configuration newConfig) {
    View decor = getWindow().getDecorView();
    WindowInsetsControllerCompat bars = WindowCompat.getInsetsController(getWindow(), decor);
    boolean lightStatus = bars.isAppearanceLightStatusBars();
    boolean lightNav = bars.isAppearanceLightNavigationBars();
    Drawable bg = decor.getBackground();
    super.onConfigurationChanged(newConfig);
    bars.setAppearanceLightStatusBars(lightStatus);
    bars.setAppearanceLightNavigationBars(lightNav);
    if (bg != null) decor.setBackground(bg);
    // 시스템 글자 크기(fontScale)를 바꾸면 액티비티를 새로 만들어 앱이 처음부터 다시 불러와지고 보던 화면·친 글이 사라졌다 (AND1-09).
    // 이제 configChanges 로 받는다. 웹뷰의 글자 확대는 만들 때의 글자 크기를 따르므로(1.3 이면 130%) 여기서 새 크기로 맞춘다.
    // 누가 따로 정해 둔 확대면(지금 값이 이전 글자 크기와 다르면) 건드리지 않는다
    if (newConfig.fontScale != fontScale && bridge != null && bridge.getWebView() != null) {
      WebSettings ws = bridge.getWebView().getSettings();
      if (ws.getTextZoom() == Math.round(fontScale * 100)) ws.setTextZoom(Math.round(newConfig.fontScale * 100));
      fontScale = newConfig.fontScale;
    }
  }

  /** 웹의 alert·confirm·prompt 를 한국어 단추(확인·취소)로 띄운다. 뒤로 키·바깥 누르기는 취소 */
  static class KoreanDialogs extends BridgeWebChromeClient {
    private final Bridge bridge;

    KoreanDialogs(Bridge bridge) {
      super(bridge);
      this.bridge = bridge;
    }

    private boolean gone(JsResult result) {
      if (bridge.getActivity() == null || bridge.getActivity().isFinishing()) { result.cancel(); return true; }
      return false;
    }

    @Override public boolean onJsAlert(WebView view, String url, String message, final JsResult result) {
      if (gone(result)) return true;
      new AlertDialog.Builder(view.getContext())
        .setMessage(message)
        .setPositiveButton("확인", (d, w) -> result.confirm())
        .setOnCancelListener(d -> result.cancel())
        .show();
      return true;
    }

    @Override public boolean onJsConfirm(WebView view, String url, String message, final JsResult result) {
      if (gone(result)) return true;
      new AlertDialog.Builder(view.getContext())
        .setMessage(message)
        .setPositiveButton("확인", (d, w) -> result.confirm())
        .setNegativeButton("취소", (d, w) -> result.cancel())
        .setOnCancelListener(d -> result.cancel())
        .show();
      return true;
    }

    @Override public boolean onJsPrompt(WebView view, String url, String message, String defaultValue, final JsPromptResult result) {
      if (gone(result)) return true;
      final EditText input = new EditText(view.getContext());
      if (defaultValue != null) input.setText(defaultValue);
      new AlertDialog.Builder(view.getContext())
        .setMessage(message)
        .setView(input)
        .setPositiveButton("확인", (d, w) -> result.confirm(input.getText().toString().trim()))
        .setNegativeButton("취소", (d, w) -> result.cancel())
        .setOnCancelListener(d -> result.cancel())
        .show();
      return true;
    }
  }
}
