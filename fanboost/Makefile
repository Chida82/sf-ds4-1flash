BIN   = /usr/local/bin/fanboost
PLIST = /Library/LaunchDaemons/com.chida82.fanboost.plist

fanboost: fanboost.c
	clang -O2 -Wall -framework IOKit -o $@ $<

test: fanboost
	./fanboost -t

install: fanboost
	-launchctl bootout system $(PLIST) 2>/dev/null
	rm -f /usr/local/sbin/fanboost  # vecchio percorso, toglibile dopo il primo install
	install -d -o root -g wheel /usr/local/bin
	install -o root -g wheel -m 755 fanboost $(BIN)
	install -o root -g wheel -m 644 com.chida82.fanboost.plist $(PLIST)
	launchctl bootstrap system $(PLIST)

# bootout manda SIGTERM: il demone rimette le ventole in AUTO prima di uscire.
uninstall:
	-launchctl bootout system $(PLIST)
	rm -f $(BIN) $(PLIST)

.PHONY: test install uninstall
