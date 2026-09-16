package com.lets1414.app;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
  @Override public void onCreate(android.os.Bundle savedInstanceState) {
    registerPlugin(PrinterPlugin.class);
    super.onCreate(savedInstanceState);
  }
}
