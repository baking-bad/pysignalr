using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.SignalR;
using System.Threading.Tasks;

using AspNetAuthExample.Controllers;

namespace AspNetAuthExample
{
    // Define a SignalR Hub for weather updates
    public class WeatherHub : Hub
    {
        // Method to send a message to all connected clients
        public async Task SendMessage(string user, string message)
        {
            await Clients.All.SendAsync("ReceiveMessage", user, message);
        }

        // Method to send a message to a specific group
        public async Task SendMessageToGroup(string groupName, string user, string message)
        {
            await Clients.Group(groupName).SendAsync("ReceiveMessage", user, message);
        }

        // Method to add a client to a group
        public async Task AddToGroup(string groupName)
        {
            await Groups.AddToGroupAsync(Context.ConnectionId, groupName);
            await Clients.Group(groupName).SendAsync("ReceiveMessage", "System", $"{Context.ConnectionId} has joined the group {groupName}.");
        }

        // Method to remove a client from a group
        public async Task RemoveFromGroup(string groupName)
        {
            await Groups.RemoveFromGroupAsync(Context.ConnectionId, groupName);
            await Clients.Group(groupName).SendAsync("ReceiveMessage", "System", $"{Context.ConnectionId} has left the group {groupName}.");
        }

        // Method to send the weather forecast to all clients
        public async Task SendWeatherForecast(string forecast)
        {
            await Clients.All.SendAsync("ReceiveWeatherForecast", forecast);
        }
    }
}
