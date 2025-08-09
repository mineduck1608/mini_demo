"""
Websocket compatibility patch for Mini SDK
This fixes the 'closed' attribute issue with newer websockets library versions
"""

import logging

def apply_websocket_patch():
    """Apply the websocket compatibility patch"""
    try:
        # Import the websocket client module after Mini SDK is loaded
        import mini.channels.websocket_client as websocket_client

        # Get all classes in the module
        classes = [getattr(websocket_client, name) for name in dir(websocket_client)
                  if isinstance(getattr(websocket_client, name), type)]

        # Find the class with the alive property that's causing issues
        for cls in classes:
            if hasattr(cls, 'alive'):
                print(f"Found websocket class: {cls.__name__}")

                # Store the original alive property
                original_alive = cls.alive

                def create_patched_alive():
                    def patched_alive(self):
                        """Patched alive property that handles websocket API changes"""
                        try:
                            if not hasattr(self, '_client') or not self._client:
                                return False

                            # Try the newer websockets API first
                            if hasattr(self._client, 'state'):
                                # Import State enum from websockets
                                try:
                                    from websockets.protocol import State
                                    return self._client.state == State.OPEN
                                except ImportError:
                                    pass

                            # Try the close_code approach
                            if hasattr(self._client, 'close_code'):
                                return self._client.close_code is None

                            # Try the old closed attribute (for backwards compatibility)
                            if hasattr(self._client, 'closed'):
                                return not self._client.closed

                            # If we can't determine the state, return True
                            # (let it fail on actual send if connection is dead)
                            return True

                        except Exception as e:
                            logging.warning(f"Error in patched alive property: {e}")
                            return False

                    return patched_alive

                # Apply the patch
                patched_alive = create_patched_alive()
                cls.alive = property(patched_alive)
                print(f"Applied websocket patch to {cls.__name__}")

    except Exception as e:
        logging.error(f"Failed to apply websocket patch: {e}")
        print(f"Websocket patch failed: {e}")

# Auto-apply patch when module is imported
if __name__ != "__main__":
    apply_websocket_patch()
