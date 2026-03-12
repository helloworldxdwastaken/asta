; Custom NSIS hooks for Asta installer

!macro CUSTOM_INSTALL
  ; Add Windows Firewall rules to allow Asta connections
  nsExec::ExecToLog 'netsh advfirewall firewall add rule name="Asta (Out)" dir=out action=allow program="$INSTDIR\Asta.exe" enable=yes'
  nsExec::ExecToLog 'netsh advfirewall firewall add rule name="Asta (In)" dir=in action=allow program="$INSTDIR\Asta.exe" enable=yes'
!macroend

!macro CUSTOM_UNINSTALL
  ; Remove Windows Firewall rules on uninstall
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="Asta (Out)"'
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="Asta (In)"'
!macroend
