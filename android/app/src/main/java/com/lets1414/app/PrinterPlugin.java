package com.lets1414.app;

import android.content.Context;
import android.print.PrintAttributes;
import android.print.PrintDocumentAdapter;
import android.print.PrintManager;
import android.webkit.WebView;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/** WebView 안에 그려 둔 인쇄 조판을 안드로이드 인쇄(또는 PDF 저장)로 넘긴다.
 *  웹의 window.print() 는 WebView 에서 아무 일도 하지 않는다. */
@CapacitorPlugin(name = "Printer")
public class PrinterPlugin extends Plugin {

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
