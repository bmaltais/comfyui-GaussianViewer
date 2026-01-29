/**
 * Enhanced OrbitControls with precision mode (Shift) and Roll support.
 * Ported and adapted from gsplat.js SPLAT.OrbitControls.
 */
export class PreciseOrbitControls {
    constructor(camera, canvas, alpha = 0.5, beta = 0.5, radius = 5, inputEnabled = true, target = null) {
        const SPLAT = window.GSPLAT;
        this.camera = camera;
        this.canvas = canvas;
        this.minAngle = -90;
        this.maxAngle = 90;
        this.minZoom = 0.1;
        this.maxZoom = 30;
        this.orbitSpeed = 1;
        this.panSpeed = 1;
        this.zoomSpeed = 1;
        this.dampening = 0.12;
        this.roll = 0;

        let _radius = radius;
        let _target = target ? target.clone() : new SPLAT.Vector3();
        let _alpha = alpha;
        let _beta = beta;

        let isDragging = false;
        let isPanning = false;
        let lastMouseX = 0;
        let lastMouseY = 0;
        let touchDistance = 0;

        const keys = {};
        let isShiftPressed = false;

        const onObjectChanged = () => {
            const euler = this.camera.rotation.toEuler();
            _alpha = -euler.y;
            _beta = -euler.x;
            const x = this.camera.position.x - _radius * Math.sin(_alpha) * Math.cos(_beta);
            const y = this.camera.position.y + _radius * Math.sin(_beta);
            const z = this.camera.position.z + _radius * Math.cos(_alpha) * Math.cos(_beta);
            _target = new SPLAT.Vector3(x, y, z);
        };

        this.camera.addEventListener("objectChanged", onObjectChanged);

        this.setCameraTarget = (t) => {
            const dx = t.x - this.camera.position.x;
            const dy = t.y - this.camera.position.y;
            const dz = t.z - this.camera.position.z;
            _radius = Math.sqrt(dx * dx + dy * dy + dz * dz);
            _beta = Math.atan2(dy, Math.sqrt(dx * dx + dz * dz));
            _alpha = -Math.atan2(dx, dz);
            _target = new SPLAT.Vector3(t.x, t.y, t.z);
        };

        const getZoomScale = () => 0.1 + 0.9 * (_radius - this.minZoom) / (this.maxZoom - this.minZoom);

        const onKeyDown = (e) => {
            keys[e.code] = true;
            if (e.code === "ArrowUp") keys.KeyW = true;
            if (e.code === "ArrowDown") keys.KeyS = true;
            if (e.code === "ArrowLeft") keys.KeyA = true;
            if (e.code === "ArrowRight") keys.KeyD = true;
            if (e.shiftKey) isShiftPressed = true;
        };

        const onKeyUp = (e) => {
            keys[e.code] = false;
            if (e.code === "ArrowUp") keys.KeyW = false;
            if (e.code === "ArrowDown") keys.KeyS = false;
            if (e.code === "ArrowLeft") keys.KeyA = false;
            if (e.code === "ArrowRight") keys.KeyD = false;
            if (!e.shiftKey) isShiftPressed = false;
        };

        const onMouseDown = (e) => {
            preventDefaults(e);
            isDragging = true;
            isPanning = e.button === 2;
            lastMouseX = e.clientX;
            lastMouseY = e.clientY;
            window.addEventListener("mouseup", onMouseUp);
        };

        const onMouseUp = (e) => {
            preventDefaults(e);
            isDragging = false;
            isPanning = false;
            window.removeEventListener("mouseup", onMouseUp);
        };

        const onMouseMove = (e) => {
            preventDefaults(e);
            if (!isDragging || !this.camera) return;
            const dx = e.clientX - lastMouseX;
            const dy = e.clientY - lastMouseY;

            const shiftMult = isShiftPressed ? 0.1 : 1.0;

            if (isPanning) {
                const zoomScale = getZoomScale();
                const panX = -dx * this.panSpeed * 0.01 * zoomScale * shiftMult;
                const panY = -dy * this.panSpeed * 0.01 * zoomScale * shiftMult;
                const rotationMatrix = SPLAT.Matrix3.RotationFromQuaternion(this.camera.rotation).buffer;
                const right = new SPLAT.Vector3(rotationMatrix[0], rotationMatrix[3], rotationMatrix[6]);
                const up = new SPLAT.Vector3(rotationMatrix[1], rotationMatrix[4], rotationMatrix[7]);
                _target = _target.add(right.multiply(panX));
                _target = _target.add(up.multiply(panY));
            } else {
                _alpha -= dx * this.orbitSpeed * 0.003 * shiftMult;
                _beta += dy * this.orbitSpeed * 0.003 * shiftMult;
                _beta = Math.min(Math.max(_beta, this.minAngle * Math.PI / 180), this.maxAngle * Math.PI / 180);
            }
            lastMouseX = e.clientX;
            lastMouseY = e.clientY;
        };

        const onWheel = (e) => {
            preventDefaults(e);
            const zoomScale = getZoomScale();
            const shiftMult = isShiftPressed ? 0.1 : 1.0;
            _radius += e.deltaY * this.zoomSpeed * 0.025 * zoomScale * shiftMult;
            _radius = Math.min(Math.max(_radius, this.minZoom), this.maxZoom);
        };

        const onTouchStart = (e) => {
            preventDefaults(e);
            if (e.touches.length === 1) {
                isDragging = true;
                isPanning = false;
                lastMouseX = e.touches[0].clientX;
                lastMouseY = e.touches[0].clientY;
                touchDistance = 0;
            } else if (e.touches.length === 2) {
                isDragging = true;
                isPanning = true;
                lastMouseX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
                lastMouseY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
                const dx = e.touches[0].clientX - e.touches[1].clientX;
                const dy = e.touches[0].clientY - e.touches[1].clientY;
                touchDistance = Math.sqrt(dx * dx + dy * dy);
            }
        };

        const onTouchEnd = (e) => {
            preventDefaults(e);
            isDragging = false;
            isPanning = false;
        };

        const onTouchMove = (e) => {
            preventDefaults(e);
            if (!isDragging || !this.camera) return;
            if (isPanning && e.touches.length === 2) {
                const zoomScale = getZoomScale();
                const dx = e.touches[0].clientX - e.touches[1].clientX;
                const dy = e.touches[0].clientY - e.touches[1].clientY;
                const distance = Math.sqrt(dx * dx + dy * dy);
                const deltaDistance = touchDistance - distance;
                const shiftMult = isShiftPressed ? 0.1 : 1.0;
                _radius += deltaDistance * this.zoomSpeed * 0.1 * zoomScale * shiftMult;
                _radius = Math.min(Math.max(_radius, this.minZoom), this.maxZoom);
                touchDistance = distance;

                const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
                const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
                const dMidX = midX - lastMouseX;
                const dMidY = midY - lastMouseY;
                const rotationMatrix = SPLAT.Matrix3.RotationFromQuaternion(this.camera.rotation).buffer;
                const right = new SPLAT.Vector3(rotationMatrix[0], rotationMatrix[3], rotationMatrix[6]);
                const up = new SPLAT.Vector3(rotationMatrix[1], rotationMatrix[4], rotationMatrix[7]);
                _target = _target.add(right.multiply(-dMidX * this.panSpeed * 0.025 * zoomScale * shiftMult));
                _target = _target.add(up.multiply(-dMidY * this.panSpeed * 0.025 * zoomScale * shiftMult));
                lastMouseX = midX;
                lastMouseY = midY;
            } else if (!isPanning && e.touches.length === 1) {
                const dx = e.touches[0].clientX - lastMouseX;
                const dy = e.touches[0].clientY - lastMouseY;
                const shiftMult = isShiftPressed ? 0.1 : 1.0;
                _alpha -= dx * this.orbitSpeed * 0.003 * shiftMult;
                _beta += dy * this.orbitSpeed * 0.003 * shiftMult;
                _beta = Math.min(Math.max(_beta, this.minAngle * Math.PI / 180), this.maxAngle * Math.PI / 180);
                lastMouseX = e.touches[0].clientX;
                lastMouseY = e.touches[0].clientY;
            }
        };

        const lerp = (a, b, t) => (1 - t) * a + t * b;

        this.update = () => {
            alpha = lerp(alpha, _alpha, this.dampening);
            beta = lerp(beta, _beta, this.dampening);
            radius = lerp(radius, _radius, this.dampening);
            target = target.lerp(_target, this.dampening);

            const x = target.x + radius * Math.sin(alpha) * Math.cos(beta);
            const y = target.y - radius * Math.sin(beta);
            const z = target.z - radius * Math.cos(alpha) * Math.cos(beta);
            this.camera.position = new SPLAT.Vector3(x, y, z);

            const dir = target.subtract(this.camera.position).normalize();
            const pitch = Math.asin(-dir.y);
            const yaw = Math.atan2(dir.x, dir.z);
            this.camera.rotation = SPLAT.Quaternion.FromEuler(new SPLAT.Vector3(pitch, yaw, this.roll));

            const moveSpeed = isShiftPressed ? 0.0025 : 0.025;
            const rotateSpeed = isShiftPressed ? 0.001 : 0.01;

            const rotationMatrix = SPLAT.Matrix3.RotationFromQuaternion(this.camera.rotation).buffer;
            const forward = new SPLAT.Vector3(-rotationMatrix[2], -rotationMatrix[5], -rotationMatrix[8]);
            const right = new SPLAT.Vector3(rotationMatrix[0], rotationMatrix[3], rotationMatrix[6]);

            if (keys.KeyS) _target = _target.add(forward.multiply(moveSpeed));
            if (keys.KeyW) _target = _target.subtract(forward.multiply(moveSpeed));
            if (keys.KeyA) _target = _target.subtract(right.multiply(moveSpeed));
            if (keys.KeyD) _target = _target.add(right.multiply(moveSpeed));
            if (keys.KeyE) _alpha += rotateSpeed;
            if (keys.KeyQ) _alpha -= rotateSpeed;
            if (keys.KeyR) _beta += rotateSpeed;
            if (keys.KeyF) _beta -= rotateSpeed;
            if (keys.KeyZ) this.roll -= rotateSpeed;
            if (keys.KeyX) this.roll += rotateSpeed;
        };

        const preventDefaults = (e) => {
            e.preventDefault();
            e.stopPropagation();
        };

        this.dispose = () => {
            this.camera.removeEventListener("objectChanged", onObjectChanged);
            canvas.removeEventListener("mousedown", onMouseDown);
            canvas.removeEventListener("mousemove", onMouseMove);
            canvas.removeEventListener("wheel", onWheel);
            canvas.removeEventListener("touchstart", onTouchStart);
            canvas.removeEventListener("touchend", onTouchEnd);
            canvas.removeEventListener("touchmove", onTouchMove);
            canvas.removeEventListener("dragenter", preventDefaults);
            canvas.removeEventListener("dragover", preventDefaults);
            canvas.removeEventListener("dragleave", preventDefaults);
            canvas.removeEventListener("contextmenu", preventDefaults);
            if (inputEnabled) {
                window.removeEventListener("keydown", onKeyDown);
                window.removeEventListener("keyup", onKeyUp);
            }
        };

        if (inputEnabled) {
            window.addEventListener("keydown", onKeyDown);
            window.addEventListener("keyup", onKeyUp);
        }
        canvas.addEventListener("mousedown", onMouseDown);
        canvas.addEventListener("mousemove", onMouseMove);
        canvas.addEventListener("wheel", onWheel);
        canvas.addEventListener("touchstart", onTouchStart);
        canvas.addEventListener("touchend", onTouchEnd);
        canvas.addEventListener("touchmove", onTouchMove);
        canvas.addEventListener("dragenter", preventDefaults);
        canvas.addEventListener("dragover", preventDefaults);
        canvas.addEventListener("dragleave", preventDefaults);
        canvas.addEventListener("contextmenu", preventDefaults);

        this.update();
    }
}
