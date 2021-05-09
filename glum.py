import json
import websockets
import asyncio
import time
from threading import Thread, Lock

from glumpy import app, gl, glm, gloo, __version__
from hand import Hand
from gesture import GestureHelper

from log import log


def render(interactive=False):

    log.info(f"Runnning glfw renderer")

    app.use("glfw")
    config = app.configuration.Configuration()
    config.samples = 16
    console = app.Console(rows=32, cols=80, scale=3, color=(1, 1, 1, 1))
    global window  # to be used to close the window
    window = app.Window(width=console.cols*console.cwidth*console.scale, height=console.rows*console.cheight*console.scale, color=(0.3, 0.3, 0.3, 1), config=config)

    @window.timer(1/60.0)
    def timer(fps):
        console.clear()
        console.write("-------------------------------------------------------")
        console.write(" Glumpy version %s" % (__version__))
        console.write(" Window size: %dx%d" % (window.width, window.height))
        console.write(" Console size: %dx%d" % (console._rows, console._cols))
        console.write(" Backend: %s (%s)" % (window._backend.__name__,
                                             window._backend.__version__))
        console.write(" Actual FPS: %.2f frames/second" % (window.fps))
        console.write(" Hit 'V' key to toggle bone view")
        console.write(" Hit 'P' key to pause or unpause")
        console.write("-------------------------------------------------------")
        for line in repr(window.config).split("\n"):
            console.write(" "+line)
        console.write("-------------------------------------------------------")

        # Rotate cube
        for hand in gesture.hand_pool:
            model = hand.key_point.program["u_model"].reshape(4, 4)
            glm.rotate(model, 1, 0, 0, 1)
            glm.rotate(model, 1, 0, 1, 0)
            hand.key_point.program['u_model'] = model

            model = hand.bone.program["u_model"].reshape(4, 4)
            glm.rotate(model, 1, 0, 1, 0)
            hand.bone.program['u_model'] = model

    @window.event
    def on_draw(dt):
        window.clear()

        console.draw()

        for hand in gesture.hand_pool:
            hand.draw()

    @window.event
    def on_resize(width, height):
        for hand in gesture.hand_pool:
            hand.resize(width, height)

    @window.event
    def on_init():
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_LINE_SMOOTH)
        gl.glPolygonOffset(1, 1)

    @window.event
    def on_close():
        global stop_websocket
        stop_websocket = True
        log.info("The user closed the renderer window")

    @window.event
    def on_character(text):
        global update_hand_obj, stop_websocket
        'A character has been typed'
        if text == "v":
            for hand in gesture.hand_pool:
                hand.show_type += 1
                hand.show_type %= 3
        elif text == 'p':
            update_hand_obj = not update_hand_obj

    sampler_thread = Thread(target=sample)
    sampler_thread.start()

    window.attach(console)
    if interactive:
        log.info(f"Running in interactive mode, run Python here freely")
        log.info(f"Use 'app.__backend__.windows()[0].close()' to close the window")
        log.info(f"Use Ctrl+D to quit the Python Interactive Shell")
    app.run(framerate=60, interactive=interactive)

    log.info(f"The render function returned")


def sample():

    async def leap_sampler():
        global stop_websocket, update_hand_obj
        uri = "ws://localhost:6437/v7.json"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"focused": True}))
            await ws.send(json.dumps({"background": True}))
            await ws.send(json.dumps({"optimizeHMD": False}))
            log.info(f"Focused on the leap motion controller...")
            end = start = previous = time.perf_counter()

            while not stop_websocket:
                # always waiting for messages
                # await asyncio.sleep(1/60)
                msg = await ws.recv()
                current = time.perf_counter()
                if current - previous < end - start:
                    # log.info(f"Skipped...")
                    continue

                msg = json.loads(msg)
                if "timestamp" in msg:
                    if len(msg["hands"]) > 0 and update_hand_obj:
                        # log.info(f"Getting {len(msg['hands'])} hands")
                        # ! transforming millimeters to meters
                        start = time.perf_counter()
                        for i in range(min(len(msg["hands"]), len(gesture.hand_pool))):
                            gesture.update(msg, i)
                        end = time.perf_counter()
                        # log.info(f"Takes {end-start} to complete the extraction task")
                    # else:
                        # log.info(f"No hands hans been found")
                else:
                    log.info(f"Getting message: {msg}")

                previous = time.perf_counter()

        log.info(f"Leap motion sampler is stopped")

    log.info(f"Running demo sampler from leap motion")
    loop = asyncio.new_event_loop()
    loop.run_until_complete(leap_sampler())
    log.info(f"Sampler runner thread exited")


def main():
    render(interactive=True)


# ! the signaler of the two threads, updated by renderer, used by sampler
stop_websocket = False
update_hand_obj = True
# * the actual hand pool, stores global hand object, updated by sampler, used by renderer
gesture = GestureHelper()

if __name__ == "__main__":
    main()
