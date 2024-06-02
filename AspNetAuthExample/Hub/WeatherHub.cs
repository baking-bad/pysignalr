using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.SignalR;
using System.Threading.Tasks;

using AspNetAuthExample.Controllers;

namespace AspNetAuthExample
{
    public class WeatherHub : Hub
    {
        // Método para enviar uma mensagem a todos os clientes conectados
        public async Task SendMessage(string user, string message)
        {
            await Clients.All.SendAsync("ReceiveMessage", user, message);
        }

        // Método para enviar uma mensagem a um grupo específico
        public async Task SendMessageToGroup(string groupName, string user, string message)
        {
            await Clients.Group(groupName).SendAsync("ReceiveMessage", user, message);
        }

        // Método para adicionar um cliente a um grupo
        public async Task AddToGroup(string groupName)
        {
            await Groups.AddToGroupAsync(Context.ConnectionId, groupName);
            await Clients.Group(groupName).SendAsync("ReceiveMessage", "System", $"{Context.ConnectionId} has joined the group {groupName}.");
        }

        // Método para remover um cliente de um grupo
        public async Task RemoveFromGroup(string groupName)
        {
            await Groups.RemoveFromGroupAsync(Context.ConnectionId, groupName);
            await Clients.Group(groupName).SendAsync("ReceiveMessage", "System", $"{Context.ConnectionId} has left the group {groupName}.");
        }

        // Método para enviar a previsão do tempo
        public async Task SendWeatherForecast(string forecast)
        {
            await Clients.All.SendAsync("ReceiveWeatherForecast", forecast);
        }
    }
}