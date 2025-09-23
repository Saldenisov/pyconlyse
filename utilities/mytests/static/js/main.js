document.getElementById("form-submit").addEventListener("click", function(event){
    event.preventDefault();
        document.getElementById("success-message").textContent = "success";
    document.getElementById("success-message").style.color = "green";
    return false;
});
