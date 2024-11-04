function validatePassword() {
    var password = document.getElementById("password1");
    var confirmPassword = document.getElementById("password2");
    var message = document.getElementById("message");

    if (password.value !== confirmPassword.value) {
        message.style.color = 'red';
        message.innerHTML = 'Passwords do not match';
        return false;
    } else {
        message.style.color = 'green';
        message.innerHTML = 'Passwords match';
        return true;
    }
}

const forms = document.querySelector(".forms"),
      pwShowHide = document.querySelectorAll(".eye-icon"),
      links = document.querySelectorAll(".link");

pwShowHide.forEach(eyeIcon => {
    eyeIcon.addEventListener("click", () => {
        let pwFields = eyeIcon.parentElement.parentElement.querySelectorAll(".password");
        
        pwFields.forEach(password => {
            if(password.type === "password"){
                password.type = "text";
                eyeIcon.classList.replace("bx-hide", "bx-show");
                return;
            }
            password.type = "password";
            eyeIcon.classList.replace("bx-show", "bx-hide");
        })
        
    })
})

links.forEach(link => {
    link.addEventListener("click", e => {
       e.preventDefault(); //preventing form submit
    })
})