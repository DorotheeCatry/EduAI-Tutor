/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./templates/**/*.html",
        "./**/*.js",
        "./**/*.py",
        "./src/**/*.{css,html,js}",
        "./static_src/**/*.{css,html,js}"
    ],
    theme: {
        extend: {
            colors: {
                primary: {
                    rose: "#C586C0",
                    blue: "#007ACC",
                    green: "#4CAF50",
                    gray: "#D4D4D4"
                },
                gray: {
                    750: "#3F3F46",
                    850: "#1F2937"
                }
            }
        }
    },
    plugins: []
}
