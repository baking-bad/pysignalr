using Microsoft.AspNetCore.Mvc;
using Microsoft.IdentityModel.Tokens;
using System;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;

namespace AspNetAuthExample.Controllers
{
    // Define the route for the API controller
    [Route("api/[controller]")]
    [ApiController]
    public class AuthController : ControllerBase
    {
        // Define the POST endpoint for login
        [HttpPost("login")]
        public IActionResult Login([FromBody] LoginModel login)
        {
            // Check if the provided username and password match the predefined values
            if (login.Username == "test" && login.Password == "password")
            {
                // Generate a JWT token if credentials are correct
                var token = GenerateToken();
                // Return the token in the response
                return Ok(new { token });
            }
            // Return Unauthorized status if credentials are incorrect
            return Unauthorized();
        }

        // Method to generate a JWT token
        private string GenerateToken()
        {
            // Define the security key using a secret key
            var securityKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes("yoursecretkeyheretoSignalRserver"));
            // Define the signing credentials using HMAC-SHA256 algorithm
            var credentials = new SigningCredentials(securityKey, SecurityAlgorithms.HmacSha256);

            // Define the claims to be included in the token
            var claims = new[]
            {
                new Claim(JwtRegisteredClaimNames.Sub, "testuser"),
                new Claim(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString())
            };

            // Create the JWT token with specified claims and expiration time
            var token = new JwtSecurityToken(
                issuer: null,
                audience: null,
                claims: claims,
                expires: DateTime.Now.AddMinutes(30),
                signingCredentials: credentials);

            // Return the serialized token as a string
            return new JwtSecurityTokenHandler().WriteToken(token);
        }
    }

    // Model to represent the login request payload
    public class LoginModel
    {
        // Username property
        public string Username { get; set; }
        // Password property
        public string Password { get; set; }
    }
}
