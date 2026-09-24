package com.lets1414.app;

import android.content.Context;
import android.net.Uri;
import android.print.PrintAttributes;
import android.print.PrintDocumentAdapter;
import android.print.PrintManager;
import android.webkit.WebView;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/** WebView 안에 그려 둔 인쇄 조판을 안드로이드 인쇄(또는 PDF 저장)로 넘긴다.
 *  웹의 window.print() 는 WebView 에서 아무 일도 하지 않는다. */
@CapacitorPlugin(name = "Printer")
public class PrinterPlugin extends Plugin {

  // 파일 내보내기(콘티 파일·MusicXML). 웹뷰의 <a download> 는 아무 일도 하지 않아서, 웹이 만든 글을
  // 캐시 폴더(exports/)에 써 두고 file:// 주소를 돌려준다 → 웹이 공유 시트(@capacitor/share)로 넘긴다.
  // 캐시 폴더는 file_paths.xml 의 cache-path 라 FileProvider 로 다른 앱에 건넬 수 있다.
  // 큰 파일은 여러 번에 나눠 온다 (append). 이름은 마지막 조각만 써서 폴더 밖으로 못 나가게 한다
  @PluginMethod
  public void saveFile(final PluginCall call) {
    writeExport(call, call.getString("data", "").getBytes(java.nio.charset.StandardCharsets.UTF_8));
  }

  // 글이 아닌 파일(합주 녹음). 웹뷰에서 바이트를 그대로 못 넘겨 base64 조각으로 온다 → 풀어서 쓴다.
  // saveFile 로 보내면 UTF-8 글로 써져 소리 파일이 깨진다
  @PluginMethod
  public void saveBytes(final PluginCall call) {
    byte[] b;
    try { b = android.util.Base64.decode(call.getString("data", ""), android.util.Base64.DEFAULT); }
    catch (IllegalArgumentException e) { call.reject("파일 조각이 이상해요"); return; }
    writeExport(call, b);
  }

  private void writeExport(PluginCall call, byte[] bytes) {
    String name = new java.io.File(call.getString("name", "1414.txt")).getName().replace(':', '_');
    if (name.isEmpty() || name.equals(".") || name.equals("..")) { call.reject("파일 이름이 이상해요"); return; }
    try {
      java.io.File dir = new java.io.File(getContext().getCacheDir(), "exports");
      if (!dir.isDirectory() && !dir.mkdirs()) { call.reject("임시 폴더를 만들지 못했어요"); return; }
      java.io.File f = new java.io.File(dir, name);
      try (java.io.OutputStream os = new java.io.FileOutputStream(f, Boolean.TRUE.equals(call.getBoolean("append", false)))) {
        os.write(bytes);
      }
      JSObject r = new JSObject();
      r.put("uri", Uri.fromFile(f).toString());
      call.resolve(r);
    } catch (Exception e) {
      call.reject(e.getMessage() == null ? "파일을 쓰지 못했어요" : e.getMessage());
    }
  }

  // 상태바 뒤 띠 = 창 배경. 안드로이드 15 부터 상태바 색 지정이 무시돼서 창 배경을 테마 색으로 칠한다
  @PluginMethod
  public void setWindowBackground(final PluginCall call) {
    final String color = call.getString("color", "#111213");
    getActivity().runOnUiThread(new Runnable() {
      @Override public void run() {
        try {
          getActivity().getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(android.graphics.Color.parseColor(color)));
          call.resolve();
        } catch (Exception e) { call.reject(e.getMessage()); }
      }
    });
  }

  @PluginMethod
  public void print(final PluginCall call) {
    final String name = call.getString("name", "1414");
    getActivity().runOnUiThread(new Runnable() {
      @Override public void run() {
        try {
          WebView wv = getBridge().getWebView();
          PrintManager pm = (PrintManager) getContext().getSystemService(Context.PRINT_SERVICE);
          if (pm == null) { call.reject("이 기기에서 인쇄를 쓸 수 없어요"); return; }
          PrintDocumentAdapter adapter = wv.createPrintDocumentAdapter(name);
          pm.print(name, adapter, new PrintAttributes.Builder().build());
          call.resolve();
        } catch (Exception e) {
          call.reject(e.getMessage() == null ? "인쇄를 열지 못했어요" : e.getMessage());
        }
      }
    });
  }
}
