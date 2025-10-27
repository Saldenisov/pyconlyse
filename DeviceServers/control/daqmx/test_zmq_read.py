"""
Test script to read ZMQ data from LabVIEW DAQmx
"""

import zmq
import json
import time

# ZMQ Configuration
ZMQ_HOST = "129.175.100.128"
ZMQ_PORT = 6050

def main():
    context = zmq.Context()
    socket = context.socket(zmq.PULL)
    
    # Bind to receive from ZMQ pusher
    zmq_address = f"tcp://*:{ZMQ_PORT}"
    print(f"Binding to {zmq_address}...")
    socket.bind(zmq_address)
    
    print("Listening for messages for 5 seconds...")
    
    start_time = time.time()
    elapsed_time = 0
    
    try:
        while elapsed_time < 5:
            # Set a timeout so we can check elapsed time
            socket.setsockopt(zmq.RCVTIMEO, 1000)  # 1 second timeout
            
            try:
                # Receive message
                message = socket.recv_string()
                print("\n" + "="*60)
                print(f"Message received at {time.time() - start_time:.2f}s")
                
                # Try to parse as JSON
                try:
                    data = json.loads(message)
                    print(f"\nReceived {len(data)} arrays:")
                    for i, array in enumerate(data):
                        non_empty = [item for item in array if item]
                        if non_empty:
                            print(f"\nArray {i} ({len(non_empty)} items):")
                            for item in non_empty[:5]:  # Show first 5 items
                                print(f"  {item}")
                            if len(non_empty) > 5:
                                print(f"  ... and {len(non_empty) - 5} more")
                except json.JSONDecodeError as e:
                    print(f"\nFailed to parse as JSON: {e}")
                    print(f"Raw message: {message[:200]}...")
            except zmq.Again:
                # Timeout occurred, continue to check elapsed time
                pass
            
            elapsed_time = time.time() - start_time
        
        print("\n\n5 seconds elapsed. Stopping...")
                
    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        socket.close()
        context.term()

if __name__ == "__main__":
    main()
