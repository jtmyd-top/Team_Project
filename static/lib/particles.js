/**
 * 粒子背景效果
 * 创建动态的粒子背景动画
 */

class ParticleBackground {
    constructor(options = {}) {
        this.options = {
            particleCount: 50,
            particleSize: { min: 2, max: 6 },
            particleSpeed: { min: 0.5, max: 2 },
            particleOpacity: { min: 0.1, max: 0.5 },
            particleColor: 'rgba(99, 102, 241, ',
            connectionDistance: 150,
            enableConnections: true,
            enableMouse: true,
            mouseRadius: 150,
            ...options
        };

        this.particles = [];
        this.canvas = null;
        this.ctx = null;
        this.animationId = null;
        this.mouse = { x: null, y: null };
        this.init();
    }

    init() {
        this.createCanvas();
        this.createParticles();
        this.bindEvents();
        this.animate();
    }

    createCanvas() {
        // 创建画布
        this.canvas = document.createElement('div');
        this.canvas.className = 'particles';
        document.body.appendChild(this.canvas);

        // 创建粒子容器
        this.particleContainer = document.createElement('div');
        this.particleContainer.className = 'particles-container';
        this.canvas.appendChild(this.particleContainer);
    }

    createParticles() {
        for (let i = 0; i < this.options.particleCount; i++) {
            this.createParticle();
        }
    }

    createParticle() {
        const particle = document.createElement('div');
        particle.className = 'particle';

        // 随机大小
        const size = this.randomBetween(
            this.options.particleSize.min,
            this.options.particleSize.max
        );

        // 随机位置
        const x = Math.random() * window.innerWidth;
        const y = Math.random() * window.innerHeight;

        // 随机速度
        const speedX = this.randomBetween(-1, 1) * this.randomBetween(
            this.options.particleSpeed.min,
            this.options.particleSpeed.max
        );
        const speedY = this.randomBetween(-1, 1) * this.randomBetween(
            this.options.particleSpeed.min,
            this.options.particleSpeed.max
        );

        // 随机透明度
        const opacity = this.randomBetween(
            this.options.particleOpacity.min,
            this.options.particleOpacity.max
        );

        // 设置样式
        particle.style.width = `${size}px`;
        particle.style.height = `${size}px`;
        particle.style.left = `${x}px`;
        particle.style.top = `${y}px`;
        particle.style.background = this.options.particleColor + opacity + ')';
        particle.style.animation = `particleFloat ${this.randomBetween(10, 20)}s linear infinite`;
        particle.style.animationDelay = `${Math.random() * 10}s`;

        // 保存粒子数据
        const particleData = {
            element: particle,
            x: x,
            y: y,
            size: size,
            speedX: speedX,
            speedY: speedY,
            opacity: opacity
        };

        this.particles.push(particleData);
        this.particleContainer.appendChild(particle);
    }

    randomBetween(min, max) {
        return Math.random() * (max - min) + min;
    }

    bindEvents() {
        if (this.options.enableMouse) {
            document.addEventListener('mousemove', (e) => {
                this.mouse.x = e.clientX;
                this.mouse.y = e.clientY;
            });

            document.addEventListener('mouseout', () => {
                this.mouse.x = null;
                this.mouse.y = null;
            });
        }

        // 窗口大小改变时重新初始化
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                this.destroy();
                this.init();
            }, 250);
        });
    }

    animate() {
        this.particles.forEach((particle, index) => {
            // 更新位置
            particle.x += particle.speedX;
            particle.y += particle.speedY;

            // 边界检测
            if (particle.x < 0 || particle.x > window.innerWidth) {
                particle.speedX = -particle.speedX;
            }
            if (particle.y < 0 || particle.y > window.innerHeight) {
                particle.speedY = -particle.speedY;
            }

            // 鼠标交互
            if (this.mouse.x !== null && this.mouse.y !== null) {
                const dx = this.mouse.x - particle.x;
                const dy = this.mouse.y - particle.y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < this.options.mouseRadius) {
                    const force = (this.options.mouseRadius - distance) / this.options.mouseRadius;
                    const forceX = (dx / distance) * force * 2;
                    const forceY = (dy / distance) * force * 2;

                    particle.x -= forceX;
                    particle.y -= forceY;
                }
            }

            // 更新元素位置
            particle.element.style.transform = `translate(${particle.x}px, ${particle.y}px)`;
        });

        // 连接粒子
        if (this.options.enableConnections) {
            this.connectParticles();
        }

        this.animationId = requestAnimationFrame(() => this.animate());
    }

    connectParticles() {
        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                const particle1 = this.particles[i];
                const particle2 = this.particles[j];

                const dx = particle1.x - particle2.x;
                const dy = particle1.y - particle2.y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < this.options.connectionDistance) {
                    const opacity = (1 - distance / this.options.connectionDistance) * 0.5;

                    // 创建连接线
                    this.createConnection(particle1, particle2, opacity);
                }
            }
        }
    }

    createConnection(particle1, particle2, opacity) {
        // 这里可以添加连接线的创建逻辑
        // 由于使用CSS动画，连接线的实现会更复杂
        // 这里只是一个示例框架
    }

    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }

        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }

        this.particles = [];
        this.canvas = null;
        this.ctx = null;
    }
}

// 简化版粒子效果（纯CSS实现）
class SimpleParticleBackground {
    constructor(container = document.body, count = 30) {
        this.container = container;
        this.count = count;
        this.particles = [];
        this.init();
    }

    init() {
        // 创建粒子容器
        const particleContainer = document.createElement('div');
        particleContainer.className = 'particles';
        this.container.appendChild(particleContainer);

        // 创建粒子
        for (let i = 0; i < this.count; i++) {
            this.createParticle(particleContainer);
        }
    }

    createParticle(container) {
        const particle = document.createElement('div');
        particle.className = 'particle';

        // 随机属性
        const size = Math.random() * 4 + 2;
        const left = Math.random() * 100;
        const animationDuration = Math.random() * 20 + 10;
        const animationDelay = Math.random() * 10;
        const opacity = Math.random() * 0.3 + 0.1;

        // 应用样式
        particle.style.width = `${size}px`;
        particle.style.height = `${size}px`;
        particle.style.left = `${left}%`;
        particle.style.background = `rgba(99, 102, 241, ${opacity})`;
        particle.style.animation = `particleFloat ${animationDuration}s linear infinite`;
        particle.style.animationDelay = `${animationDelay}s`;

        container.appendChild(particle);
        this.particles.push(particle);
    }

    destroy() {
        this.particles.forEach(particle => {
            if (particle.parentNode) {
                particle.parentNode.removeChild(particle);
            }
        });
        this.particles = [];
    }
}

// 自动初始化（可选）
document.addEventListener('DOMContentLoaded', () => {
    // 只在非移动设备上启用粒子效果
    if (window.innerWidth > 768) {
        // 可以根据需要选择不同的粒子效果
        const particleBg = new SimpleParticleBackground();
    }
});

// 导出给其他脚本使用
window.ParticleBackground = ParticleBackground;
window.SimpleParticleBackground = SimpleParticleBackground;